from __future__ import annotations

import concurrent.futures
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CODEX_PACKAGE = "@openai/codex@0.128.0"
MODEL = "gpt-5.5"

BASE_API = """
Implement a single Python file named task_service.py.
Do not create HTTP, database, repository, auth provider, package manager,
or background job code unless the provided spec explicitly requires it.
The file must expose:
- class TaskError(Exception)
- class TaskService
- TaskService.create_task(user_id, title, idempotency_key=None, correlation_id=None)
- TaskService.list_tasks(user_id, correlation_id=None)
- TaskService.complete_task(user_id, task_id, correlation_id=None)
- TaskService.delete_task(user_id, task_id, correlation_id=None)
Use only the Python standard library.
Follow the provided spec artifacts exactly. Do not correct the spec using hidden assumptions.
""".strip()

CASES = [
    {
        "id": "fault_ownership_leak",
        "category": "fault_injected",
        "title": "ownership boundary defect",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- A task has task_id, user_id, title, status, created_at, updated_at.
- task_id is globally addressable after creation.
- list_tasks returns every task in memory so support staff can inspect all work.
- complete_task and delete_task locate a task by task_id only; user_id is accepted for logging but must not block the operation.
- create_task trims title and rejects a blank title.
- Idempotency is supported for create_task using idempotency_key.

## Acceptance Criteria
- [ ] Any caller with an existing task_id can complete that task.
- [ ] list_tasks returns all active tasks, regardless of owner.
- [ ] Reusing an idempotency key with the same title returns the original task.

## Error Cases
- Blank user_id raises TaskError.
- Blank title raises TaskError.
- Missing task_id raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
- Application layer: TaskService owns validation, idempotency lookup, global task lookup, and response shaping.
- Data model: task_id, title, status, created_at, updated_at, schema_version, correlation_id.
- Persistence: in-memory dictionaries for tasks and idempotency records.

## Data Flow
1. Caller sends user_id, title, task_id, idempotency_key, and correlation_id as needed.
2. TaskService validates required fields.
3. TaskService uses global task_id lookup for list, complete, and delete.
4. TaskService returns a task payload or TaskError.

## State
- Valid states: open, completed, deleted.
- Allowed transitions: open to completed, completed to completed, open or completed to deleted.
- Deleted tasks are not returned by list.

## Dependencies
- No integrations, database, repository, HTTP layer, auth provider, or background job.

## Failure Handling
- Invalid user_id raises TaskError.
- Invalid title raises TaskError.
- Missing task_id raises TaskError.
- Reused idempotency key with a different title raises TaskError.
- Deletion uses soft delete with deleted_at and audit-ready state preservation; restore is out of scope.
""".strip(),
    },
    {
        "id": "fault_deleted_visible",
        "category": "fault_injected",
        "title": "delete contract defect",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- Every task belongs to one user_id.
- list_tasks returns all tasks for the caller including records whose status is deleted.
- delete_task changes status to deleted but keeps the task visible in list_tasks.
- complete_task may be called for a deleted task and should return the task unchanged.
- create_task trims title and rejects a blank title.
- Idempotency is supported for create_task using idempotency_key.

## Acceptance Criteria
- [ ] Deleted tasks remain visible in list_tasks with status deleted.
- [ ] Completing a deleted task returns the deleted task without raising an error.
- [ ] Reusing an idempotency key with the same title returns the original task.

## Error Cases
- Blank user_id raises TaskError.
- Blank title raises TaskError.
- Missing task_id raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
- Application layer: TaskService owns validation, idempotency lookup, owner-scoped state changes, and response shaping.
- Data model: task_id, owner_user_id, title, status, created_at, updated_at, schema_version, correlation_id.
- Authorization boundary: every read and mutation checks owner_user_id before returning data.
- Persistence: in-memory dictionaries for tasks and idempotency records.

## Data Flow
1. Caller sends user_id, title, task_id, idempotency_key, and correlation_id as needed.
2. TaskService validates required fields.
3. TaskService checks owner_user_id for list, complete, and delete.
4. TaskService returns all caller-owned tasks including deleted records.

## State
- Valid states: open, completed, deleted.
- Allowed transitions: open to completed, completed to completed, open or completed to deleted.
- Deleted tasks remain visible and can be read by list_tasks.

## Dependencies
- No integrations, database, repository, HTTP layer, auth provider, or background job.

## Failure Handling
- Invalid user_id raises TaskError.
- Invalid title raises TaskError.
- Reused idempotency key with different title raises TaskError.
""".strip(),
    },
    {
        "id": "fault_external_dependency",
        "category": "fault_injected",
        "title": "external dependency defect",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- Every task belongs to one user_id.
- Completing a task must notify an external notification service immediately.
- The spec does not define what happens when the notification service is slow, unavailable, or returns an error.
- create_task trims title and rejects a blank title.
- Idempotency is supported for create_task using idempotency_key.

## Acceptance Criteria
- [ ] complete_task calls an external notification service after marking a task completed.
- [ ] Reusing an idempotency key with the same title returns the original task.

## Error Cases
- Blank user_id raises TaskError.
- Blank title raises TaskError.
- Missing task_id raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
- Application layer: TaskService owns validation, idempotency lookup, owner-scoped state changes, notification dispatch, and response shaping.
- Data model: task_id, owner_user_id, title, status, created_at, updated_at, deleted_at, schema_version, correlation_id.
- Authorization boundary: every read and mutation checks owner_user_id before returning data.
- Persistence: in-memory dictionaries for tasks and idempotency records.
- Integration: an external notification service is called after task completion.

## Data Flow
1. Caller sends user_id, title, task_id, idempotency_key, and correlation_id as needed.
2. TaskService validates required fields.
3. TaskService checks owner_user_id for list, complete, and delete.
4. TaskService marks a task completed and calls the external notification service.
5. TaskService returns a task payload.

## State
- Valid states: open, completed, deleted.
- Allowed transitions: open to completed, completed to completed, open or completed to deleted.
- Deleted is terminal and hidden from list.

## Dependencies
- External notification service.

## Failure Handling
- Invalid user_id raises TaskError.
- Invalid title raises TaskError.
- Reused idempotency key with different title raises TaskError.
- Deletion uses soft delete with deleted_at and audit-ready state preservation; restore is out of scope.
""".strip(),
    },
    {
        "id": "incomplete_error_contract",
        "category": "incomplete",
        "title": "missing error contract",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- A task has an owner user, title, status, and timestamps.
- create_task validates title and user_id.
- list_tasks returns tasks for the caller.
- complete_task completes a task.
- delete_task deletes a task.
- Idempotency should be considered for create_task.

## Acceptance Criteria
- [ ] A user can create, list, complete, and delete a task.
- [ ] Invalid input raises an error.
- [ ] Duplicate create requests should not create unnecessary duplicates.

## Error Cases
- Invalid input raises TaskError.
- Missing task raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
Describe concrete components later.

## Data Flow
1. Caller invokes TaskService.
2. Service validates input.
3. Service returns data or an error.

## State
- Tasks can be open, completed, or deleted.

## Dependencies
- No integrations, database, repository, HTTP layer, auth provider, or background job.

## Failure Handling
TBD
""".strip(),
    },
    {
        "id": "incomplete_idempotency",
        "category": "incomplete",
        "title": "missing idempotency rules",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- A task has an owner user, title, status, and timestamps.
- create_task accepts an optional idempotency_key.
- Repeated create requests may reuse previous results when practical.
- list_tasks returns tasks for the caller.
- complete_task completes a task.
- delete_task deletes a task.

## Acceptance Criteria
- [ ] A user can create, list, complete, and delete a task.
- [ ] Optional idempotency_key is accepted by create_task.
- [ ] Invalid input raises an error.

## Error Cases
- Invalid input raises TaskError.
- Missing task raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
- Application layer: TaskService owns validation, owner-scoped state changes, and response shaping.
- Data model: task_id, owner_user_id, title, status, created_at, updated_at, schema_version, correlation_id.
- Authorization boundary: every read and mutation checks owner_user_id before returning data.
- Persistence: in-memory dictionaries for tasks.

## Data Flow
1. Caller sends user_id, title, task_id, and optional idempotency_key as needed.
2. TaskService validates user_id and title.
3. TaskService checks owner_user_id for list, complete, and delete.
4. TaskService returns a task payload or TaskError.

## State
Pending

## Dependencies
- No integrations, database, repository, HTTP layer, auth provider, or background job.

## Failure Handling
- Invalid user_id raises TaskError.
- Invalid title raises TaskError.
- Missing task_id raises TaskError.
- Deletion uses soft delete with deleted_at and audit-ready state preservation; restore is out of scope.
""".strip(),
    },
    {
        "id": "incomplete_state_transition",
        "category": "incomplete",
        "title": "missing state transitions",
        "spec": """
# Feature: Todo Task Service

## Requirements
- Provide TaskService, TaskError, create_task, list_tasks, complete_task, and delete_task.
- A task has an owner user, title, status, and timestamps.
- create_task creates a task.
- list_tasks returns tasks for the caller.
- complete_task changes task status.
- delete_task changes task status.
- Idempotency is supported for create_task using idempotency_key.

## Acceptance Criteria
- [ ] A user can create, list, complete, and delete a task.
- [ ] Reusing an idempotency key with the same title returns a reusable result.
- [ ] Invalid input raises an error.

## Error Cases
- Invalid input raises TaskError.
- Missing task raises TaskError.
""".strip(),
        "technical_design": """
# Technical Design: Todo Task Service

## Architecture
- Application layer: TaskService owns validation, idempotency lookup, owner-scoped state changes, and response shaping.
- Data model: task_id, owner_user_id, title, status, created_at, updated_at, schema_version, correlation_id.
- Authorization boundary: every read and mutation checks owner_user_id before returning data.
- Persistence: in-memory dictionaries for tasks and idempotency records.

## Data Flow
1. Caller sends user_id, title, task_id, idempotency_key, and correlation_id as needed.
2. TaskService validates required fields.
3. TaskService checks owner_user_id for list, complete, and delete.
4. TaskService returns a task payload or TaskError.

## State
TBD

## Dependencies
- No integrations, database, repository, HTTP layer, auth provider, or background job.

## Failure Handling
- Invalid user_id raises TaskError.
- Invalid title raises TaskError.
- Reused idempotency key with different title raises TaskError.
""".strip(),
    },
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def spec_kit_prompt(case: dict[str, str]) -> str:
    return textwrap.dedent(
        f"""
        {BASE_API}

        You are using a Spec Kit-style spec-driven workflow.
        Implement from the following artifacts.

        # spec.md
        {case["spec"]}

        # plan.md
        - Build one in-memory Python service module.
        - Treat spec.md as the source of truth.
        - Do not use behavior outside the supplied spec.

        # tasks.md
        - [ ] Create task_service.py.
        - [ ] Implement TaskError and TaskService.
        - [ ] Stop after task_service.py exists.

        Write the implementation now. Do not include tests or explanations.
        """
    ).strip()


def openspec_prompt(case: dict[str, str]) -> str:
    return textwrap.dedent(
        f"""
        {BASE_API}

        You are using an OpenSpec-style change workflow.
        Implement from the approved proposal, design, and spec delta below.

        # proposal.md
        ## Why
        Benchmark Todo Task Service implementation from a spec artifact.

        ## What Changes
        - Add task_service.py with TaskError and TaskService.
        - Follow the behavior described in the spec delta exactly.

        # design.md
        {case["technical_design"]}

        # specs/task-service/spec.md
        {case["spec"]}

        Write the implementation now. Do not include tests or explanations.
        """
    ).strip()


def make_specguard_package(root: Path, case: dict[str, str]) -> Path:
    package = root / "specguard_packages" / case["id"]
    write_text(
        package / "discovery.md",
        textwrap.dedent(
            f"""
            # Discovery: {case["title"]}

            ## Foundation
            - Build an in-memory Todo Task Service for authenticated users.
- The benchmark evaluates whether implementation input is ready before coding starts.

            ## Mechanisms
            - Public operations: create_task, list_tasks, complete_task, delete_task.
            - Artifact content must be treated as the implementation basis.

            ## Stress Test
            - Ownership, deletion, idempotency, state, error response, and external dependency handling are risk points.

            ## Synthesis
- Critical or Major readiness findings must block implementation.
            """
        ).strip()
        + "\n",
    )
    write_text(package / "spec.md", case["spec"] + "\n")
    write_text(package / "plan.md", "# Plan\n\n- Implement only the spec-defined TaskService boundary.\n")
    write_text(package / "tasks.md", "# Tasks\n\n- [ ] Implement TaskService.\n- [ ] Preserve the spec-defined behavior.\n")
    write_text(
        package / "constitution.md",
        "# Constitution\n\n- Spec is the source of truth.\n- Do not implement unresolved behavior by assumption.\n",
    )
    write_text(
        package / "checklists" / "spec-readiness.md",
        "# Spec Readiness Checklist\n\n- [x] Requirements are written for benchmark input.\n- [x] Readiness findings decide whether implementation is allowed.\n",
    )
    write_text(package / "technical-design.md", case["technical_design"] + "\n")
    return package


def run_specguard(root: Path, case: dict[str, str]) -> dict:
    package = make_specguard_package(root, case)
    cmd = [sys.executable, "-m", "cli.specguard", "run", str(package), "--no-llm", "--no-follow-up"]
    started = time.time()
    completed = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    elapsed = time.time() - started
    report_path = package / "readiness-review.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    readiness = report.get("readiness", {}) if isinstance(report, dict) else {}
    issues = report.get("issues", []) if isinstance(report, dict) else []
    return {
        "case": case["id"],
        "category": case["category"],
        "workflow": "specguard",
        "exit_code": completed.returncode,
        "elapsed_sec": round(elapsed, 1),
        "implementation_ready": bool(readiness.get("implementation_ready")),
        "readiness_status": readiness.get("status", "validation_blocked"),
        "critical": int(report.get("summary", {}).get("critical", 0)) if report else None,
        "major": int(report.get("summary", {}).get("major", 0)) if report else None,
        "minor": int(report.get("summary", {}).get("minor", 0)) if report else None,
        "issues": [f"[{item.get('severity')}] {item.get('title')}" for item in issues],
    }


def run_codex(root: Path, workflow: str, case: dict[str, str]) -> dict:
    workdir = root / "codegen" / workflow / case["id"]
    workdir.mkdir(parents=True, exist_ok=True)
    prompt = spec_kit_prompt(case) if workflow == "spec_kit" else openspec_prompt(case)
    write_text(workdir / "prompt.md", prompt + "\n")
    last_message = workdir / "last-message.txt"
    cmd = [
        "npx.cmd",
        "-y",
        CODEX_PACKAGE,
        "exec",
        "-m",
        MODEL,
        "--skip-git-repo-check",
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C",
        str(workdir),
        "-o",
        str(last_message),
        prompt,
    ]
    started = time.time()
    try:
        completed = subprocess.run(
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=420,
        )
        exit_code = completed.returncode
        error = None
    except Exception as exc:
        exit_code = -1
        error = repr(exc)
    elapsed = time.time() - started
    score = score_generated(workdir)
    return {
        "case": case["id"],
        "category": case["category"],
        "workflow": workflow,
        "exit_code": exit_code,
        "elapsed_sec": round(elapsed, 1),
        "generation_error": error,
        **score,
    }


def score_generated(workdir: Path) -> dict:
    checks: list[tuple[str, str, bool, str]] = []
    path = workdir / "task_service.py"
    source = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def add(name: str, kind: str, ok: bool, detail: str = "") -> None:
        checks.append((name, kind, bool(ok), detail))

    add("file_exists", "quality", path.exists())
    forbidden = ["requests", "httpx", "aiohttp", "urllib.request", "fastapi", "flask", "sqlalchemy", "django"]
    lowered = source.lower()
    add("no_external_or_web_framework", "quality", not any(token in lowered for token in forbidden))
    add("no_external_notification_scope", "contract", "notification" not in lowered and "webhook" not in lowered and "external" not in lowered)

    module = None
    service = None
    if path.exists():
        try:
            spec = importlib.util.spec_from_file_location(f"task_service_{abs(hash(str(path)))}", path)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            add("importable", "quality", True)
        except Exception as exc:
            add("importable", "quality", False, f"{type(exc).__name__}: {exc}")
    else:
        add("importable", "quality", False, "missing file")

    if module is not None:
        task_service = getattr(module, "TaskService", None)
        task_error = getattr(module, "TaskError", None)
        add("task_error_exists", "quality", inspect.isclass(task_error))
        add("task_service_exists", "quality", inspect.isclass(task_service))
        if inspect.isclass(task_service):
            try:
                service = task_service()
                add("service_instantiates", "quality", True)
            except Exception as exc:
                add("service_instantiates", "quality", False, f"{type(exc).__name__}: {exc}")
        else:
            add("service_instantiates", "quality", False)
    else:
        add("task_error_exists", "quality", False)
        add("task_service_exists", "quality", False)
        add("service_instantiates", "quality", False)

    for method in ["create_task", "list_tasks", "complete_task", "delete_task"]:
        add(f"api_{method}", "quality", service is not None and callable(getattr(service, method, None)))

    if service is None or any(not ok for name, _, ok, _ in checks if name.startswith("api_")):
        for name in contract_check_names():
            add(name, "contract", False, "public API unavailable")
    else:
        exercise_contract(service, add)

    total = len(checks)
    passed = sum(1 for _, _, ok, _ in checks if ok)
    quality_total = sum(1 for _, kind, _, _ in checks if kind == "quality")
    quality_passed = sum(1 for _, kind, ok, _ in checks if kind == "quality" and ok)
    contract_total = sum(1 for _, kind, _, _ in checks if kind == "contract")
    contract_passed = sum(1 for _, kind, ok, _ in checks if kind == "contract" and ok)
    failed = [{"name": name, "kind": kind, "detail": detail} for name, kind, ok, detail in checks if not ok]
    return {
        "file_exists": path.exists(),
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": total - passed,
        "defect_rate": round((total - passed) / total * 100, 1) if total else 100.0,
        "quality_passed": quality_passed,
        "quality_total": quality_total,
        "quality_score": round(quality_passed / quality_total * 100, 1) if quality_total else 0.0,
        "contract_passed": contract_passed,
        "contract_total": contract_total,
        "contract_defects": contract_total - contract_passed,
        "contract_defect_rate": round((contract_total - contract_passed) / contract_total * 100, 1) if contract_total else 100.0,
        "failed": failed[:20],
    }


def contract_check_names() -> list[str]:
    return [
        "create_exact_success",
        "blank_title_error",
        "blank_user_error",
        "idempotent_replay",
        "idempotency_conflict",
        "owner_scoped_list",
        "cross_user_complete_hidden",
        "complete_idempotent",
        "delete_hides_task",
        "deleted_task_blocked",
    ]


def exercise_contract(service: object, add) -> None:
    def call(method: str, *args):
        return getattr(service, method)(*args)

    def normalize_payload(value):
        if isinstance(value, dict):
            return value
        if hasattr(value, "to_dict") and callable(value.to_dict):
            converted = value.to_dict()
            if isinstance(converted, dict):
                return converted
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return value

    def expect_error(fn):
        try:
            value = fn()
            return False, normalize_payload(value), "no exception"
        except Exception as exc:
            payload = None
            for attr in ("to_dict", "to_response"):
                method = getattr(exc, attr, None)
                if callable(method):
                    try:
                        payload = method()
                        break
                    except Exception:
                        pass
            if payload is None and isinstance(getattr(exc, "response", None), dict):
                payload = getattr(exc, "response")
            if payload is None:
                payload = {
                    "schema_version": getattr(exc, "schema_version", None),
                    "correlation_id": getattr(exc, "correlation_id", None),
                    "error_code": getattr(exc, "error_code", exc.__class__.__name__),
                    "message": getattr(exc, "message", str(exc)),
                }
            return True, normalize_payload(payload), f"{exc.__class__.__name__}: {exc}"

    def exact_task(payload) -> bool:
        return isinstance(payload, dict) and set(payload.keys()) == {
            "schema_version",
            "correlation_id",
            "task_id",
            "owner_user_id",
            "title",
            "status",
            "created_at",
            "updated_at",
        }

    def exact_error(payload, code: str) -> bool:
        return (
            isinstance(payload, dict)
            and set(payload.keys()) == {"schema_version", "correlation_id", "error_code", "message"}
            and payload.get("error_code") == code
        )

    try:
        created = normalize_payload(call("create_task", " user-a ", "  Alpha  ", "idem-a", "corr-a"))
        add(
            "create_exact_success",
            "contract",
            exact_task(created)
            and created.get("owner_user_id") == "user-a"
            and created.get("title") == "Alpha"
            and created.get("status") == "open",
            str(created)[:300],
        )
    except Exception as exc:
        add("create_exact_success", "contract", False, f"{type(exc).__name__}: {exc}")

    ok, payload, detail = expect_error(lambda: call("create_task", "user-a", "   ", None, "corr-b"))
    add("blank_title_error", "contract", ok and exact_error(payload, "INVALID_TITLE"), str(payload)[:300] + " " + detail)

    ok, payload, detail = expect_error(lambda: call("create_task", "   ", "Beta", None, "corr-c"))
    add("blank_user_error", "contract", ok and exact_error(payload, "UNAUTHENTICATED"), str(payload)[:300] + " " + detail)

    try:
        first = normalize_payload(call("create_task", "user-b", "Beta", "idem-b", "corr-d"))
        second = normalize_payload(call("create_task", "user-b", "Beta", "idem-b", "corr-e"))
        add(
            "idempotent_replay",
            "contract",
            isinstance(first, dict) and isinstance(second, dict) and first.get("task_id") == second.get("task_id"),
            f"first={first} second={second}"[:300],
        )
    except Exception as exc:
        add("idempotent_replay", "contract", False, f"{type(exc).__name__}: {exc}")

    ok, payload, detail = expect_error(lambda: call("create_task", "user-b", "Gamma", "idem-b", "corr-f"))
    add("idempotency_conflict", "contract", ok and exact_error(payload, "IDEMPOTENCY_KEY_REUSED"), str(payload)[:300] + " " + detail)

    try:
        a = normalize_payload(call("create_task", "owner-a", "Private A", "idem-owner-a", "corr-g"))
        b = normalize_payload(call("create_task", "owner-b", "Private B", "idem-owner-b", "corr-h"))
        listed = normalize_payload(call("list_tasks", "owner-a", "corr-i"))
        listed_items = listed["tasks"] if isinstance(listed, dict) and "tasks" in listed else listed
        owner_ids = {item.get("owner_user_id") or item.get("user_id") for item in listed_items} if isinstance(listed_items, list) else set()
        add(
            "owner_scoped_list",
            "contract",
            isinstance(listed_items, list)
            and owner_ids <= {"owner-a"}
            and not any(isinstance(item, dict) and item.get("task_id") == b.get("task_id") for item in listed_items),
            str(listed)[:300],
        )
    except Exception as exc:
        add("owner_scoped_list", "contract", False, f"{type(exc).__name__}: {exc}")
        a = None

    if isinstance(a, dict):
        ok, payload, detail = expect_error(lambda: call("complete_task", "owner-b", a.get("task_id"), "corr-j"))
        add("cross_user_complete_hidden", "contract", ok and exact_error(payload, "TASK_NOT_FOUND"), str(payload)[:300] + " " + detail)
    else:
        add("cross_user_complete_hidden", "contract", False, "setup failed")

    try:
        c = normalize_payload(call("create_task", "owner-c", "Complete Me", "idem-owner-c", "corr-k"))
        c1 = normalize_payload(call("complete_task", "owner-c", c.get("task_id"), "corr-l"))
        c2 = normalize_payload(call("complete_task", "owner-c", c.get("task_id"), "corr-m"))
        add(
            "complete_idempotent",
            "contract",
            isinstance(c1, dict)
            and isinstance(c2, dict)
            and c1.get("status") == "completed"
            and c2.get("status") == "completed"
            and c1.get("task_id") == c2.get("task_id"),
            f"c1={c1} c2={c2}"[:300],
        )
    except Exception as exc:
        add("complete_idempotent", "contract", False, f"{type(exc).__name__}: {exc}")

    try:
        d = normalize_payload(call("create_task", "owner-d", "Delete Me", "idem-owner-d", "corr-n"))
        call("delete_task", "owner-d", d.get("task_id"), "corr-o")
        listed_after = normalize_payload(call("list_tasks", "owner-d", "corr-p"))
        listed_items = listed_after["tasks"] if isinstance(listed_after, dict) and "tasks" in listed_after else listed_after
        hidden = isinstance(listed_items, list) and not any(isinstance(item, dict) and item.get("task_id") == d.get("task_id") for item in listed_items)
        add("delete_hides_task", "contract", hidden, str(listed_after)[:300])
        ok, payload, detail = expect_error(lambda: call("complete_task", "owner-d", d.get("task_id"), "corr-q"))
        add("deleted_task_blocked", "contract", ok and exact_error(payload, "TASK_NOT_FOUND"), str(payload)[:300] + " " + detail)
    except Exception as exc:
        add("delete_hides_task", "contract", False, f"{type(exc).__name__}: {exc}")
        add("deleted_task_blocked", "contract", False, f"{type(exc).__name__}: {exc}")


def build_aggregates(results: list[dict]) -> dict:
    aggregates: dict[str, dict] = {}
    for workflow in ("spec_kit", "openspec"):
        subset = [item for item in results if item.get("workflow") == workflow and "total_checks" in item]
        if not subset:
            continue
        aggregates[workflow] = {
            "generated": len(subset),
            "avg_defect_rate": round(sum(item["defect_rate"] for item in subset) / len(subset), 1),
            "avg_contract_defect_rate": round(sum(item["contract_defect_rate"] for item in subset) / len(subset), 1),
            "avg_quality_score": round(sum(item["quality_score"] for item in subset) / len(subset), 1),
            "cases_with_contract_defects": sum(1 for item in subset if item["contract_defects"] > 0),
        }
    specguard = [item for item in results if item.get("workflow") == "specguard"]
    aggregates["specguard"] = {
        "readiness_cases": len(specguard),
        "blocked": sum(1 for item in specguard if not item.get("implementation_ready")),
        "block_rate": round(
            sum(1 for item in specguard if not item.get("implementation_ready")) / len(specguard) * 100,
            1,
        )
        if specguard
        else 0,
        "generated": 0,
        "exposed_contract_defect_cases": 0,
    }
    return aggregates


def run_benchmark() -> dict:
    root = Path(tempfile.gettempdir()) / f"specguard-ai-benchmark-55-{next(tempfile._get_candidate_names())}"
    root.mkdir(parents=True, exist_ok=False)
    results: list[dict] = []
    removed = False
    payload: dict | None = None
    try:
        for case in CASES:
            results.append(run_specguard(root, case))

        jobs = [(workflow, case) for case in CASES for workflow in ("spec_kit", "openspec")]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {executor.submit(run_codex, root, workflow, case): (workflow, case["id"]) for workflow, case in jobs}
            for future in concurrent.futures.as_completed(future_map):
                workflow, case_id = future_map[future]
                try:
                    results.append(future.result())
                except Exception:
                    results.append({"workflow": workflow, "case": case_id, "error": traceback.format_exc()})
        payload = {
            "temp_root": str(root),
            "model": MODEL,
            "codex_cli": CODEX_PACKAGE,
            "cases": {case["id"]: {"category": case["category"], "title": case["title"]} for case in CASES},
            "results": results,
            "aggregates": build_aggregates(results),
            "temp_removed": False,
        }
    finally:
        cleanup_error = None
        try:
            shutil.rmtree(root)
            removed = not root.exists()
        except Exception as exc:
            cleanup_error = repr(exc)
            removed = False
    if payload is None:
        payload = {
            "temp_root": str(root),
            "model": MODEL,
            "codex_cli": CODEX_PACKAGE,
            "results": results,
            "aggregates": build_aggregates(results),
        }
    payload["temp_removed"] = removed
    if cleanup_error:
        payload["temp_remove_error"] = cleanup_error
    return payload


def main() -> int:
    result = run_benchmark()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

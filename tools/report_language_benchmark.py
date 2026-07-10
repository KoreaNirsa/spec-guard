from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.readiness_engine import run_readiness_review
from tools.report_language import localized_issue_title, report_language_from_payload
from tools.tdd_generator import generate_tests


REPORT_LANGUAGE_BENCHMARK_SCHEMA = "specguard-report-language-benchmark/v1"

REPORT_LANGUAGE_SCENARIOS = (
    {
        "id": "korean_conversation_english_spec",
        "authored_language": "en",
        "conversation_language": "ko",
        "expected": {"code": "ko", "source": "conversation", "fallback_used": False},
    },
    {
        "id": "english_conversation_korean_spec",
        "authored_language": "ko",
        "conversation_language": "en",
        "expected": {"code": "en", "source": "conversation", "fallback_used": False},
    },
    {
        "id": "no_conversation_korean_spec",
        "authored_language": "ko",
        "conversation_language": None,
        "expected": {"code": "ko", "source": "spec", "fallback_used": False},
    },
    {
        "id": "no_conversation_english_spec",
        "authored_language": "en",
        "conversation_language": None,
        "expected": {"code": "en", "source": "spec", "fallback_used": False},
    },
    {
        "id": "mixed_conversation_decisive_korean_spec",
        "authored_language": "ko",
        "conversation_language": "hello 안녕",
        "expected": {"code": "ko", "source": "spec", "fallback_used": False},
    },
    {
        "id": "mixed_conversation_inconclusive_spec",
        "authored_language": "inconclusive",
        "conversation_language": "hello 안녕",
        "expected": {"code": "en", "source": "fallback", "fallback_used": True},
    },
    {
        "id": "unsupported_short_code_inconclusive_spec",
        "authored_language": "inconclusive",
        "conversation_language": "ja",
        "expected": {"code": "en", "source": "fallback", "fallback_used": True},
    },
)


def _package_content(language: str) -> dict[str, str]:
    if language == "ko":
        return {
            "discovery.md": "# 탐색\n\n사용자는 자신의 작업을 안전하게 관리합니다.\n",
            "spec.md": "# 스펙\n\n사용자는 자신의 작업을 생성하고 조회합니다.\n",
            "technical-design.md": "# 기술 설계\n\n서비스가 요청을 처리합니다.\n",
        }
    if language == "inconclusive":
        return {
            "discovery.md": "안녕 hello\n",
            "spec.md": "세계 world\n",
            "technical-design.md": "상태 state\n",
        }
    return {
        "discovery.md": "# Discovery\n\nUsers manage their own tasks safely.\n",
        "spec.md": "# Spec\n\nUsers create and list their own tasks.\n",
        "technical-design.md": "# Technical Design\n\nThe service handles each request.\n",
    }


def _write_package(path: Path, language: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for name, content in _package_content(language).items():
        path.joinpath(name).write_text(content, encoding="utf-8")


def _authored_hashes(path: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256(path.joinpath(name).read_bytes()).hexdigest()
        for name in ("discovery.md", "spec.md", "technical-design.md")
    }


def _without_report_language(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_report_language(item)
            for key, item in value.items()
            if key != "report_language"
        }
    if isinstance(value, list):
        return [_without_report_language(item) for item in value]
    return value


def _read_report(path: Path) -> dict[str, Any]:
    return json.loads(path.joinpath("readiness-review.json").read_text(encoding="utf-8"))


def _machine_summary(payload: dict[str, Any]) -> dict[str, Any]:
    readiness = payload.get("readiness", {})
    issues = payload.get("issues", [])
    return {
        "status": readiness.get("status"),
        "implementation_ready": readiness.get("implementation_ready"),
        "severity_counts": payload.get("summary", {}),
        "issue_severities": [issue.get("severity") for issue in issues],
    }


def _human_checks(payload: dict[str, Any], report: str, language: str) -> dict[str, bool]:
    issues = payload.get("issues", [])
    known_title_localized = True
    if issues:
        title = str(issues[0].get("title", ""))
        localized_title = localized_issue_title(title, language)
        known_title_localized = localized_title in report and (
            language != "ko" or localized_title != title
        )
    if language == "ko":
        return {
            "heading_localized": report.startswith("# SpecGuard 검토 결과"),
            "guidance_localized": "## 개선 제안" in report,
            "known_title_localized": known_title_localized,
        }
    return {
        "heading_localized": report.startswith("# SpecGuard Review Result"),
        "guidance_localized": "## Improvement Suggestions" in report,
        "known_title_localized": known_title_localized,
    }


def _run_resolution_scenario(root: Path, scenario: dict[str, Any]) -> dict[str, Any]:
    path = root / str(scenario["id"])
    _write_package(path, str(scenario["authored_language"]))
    before_hashes = _authored_hashes(path)

    run_readiness_review(path, conversation_language="en")
    baseline = _read_report(path)
    conversation_language = scenario["conversation_language"]
    run_readiness_review(
        path,
        conversation_language=conversation_language if conversation_language is not None else "",
    )
    payload = _read_report(path)
    report = path.joinpath("readiness-review.md").read_text(encoding="utf-8")
    resolution = payload.get("report_language", {})
    machine_invariant = _without_report_language(payload) == _without_report_language(baseline)
    authored_files_unchanged = before_hashes == _authored_hashes(path)
    human_checks = _human_checks(payload, report, str(resolution.get("code", "en")))

    return {
        "id": scenario["id"],
        "authored_language": scenario["authored_language"],
        "conversation_language": scenario["conversation_language"],
        "expected_resolution": scenario["expected"],
        "actual_resolution": resolution,
        "resolution_matches": resolution == scenario["expected"],
        "baseline": _machine_summary(baseline),
        "result": _machine_summary(payload),
        "machine_contract_invariant": machine_invariant,
        "authored_files_unchanged": authored_files_unchanged,
        "human_checks": human_checks,
        "passed": (
            resolution == scenario["expected"]
            and machine_invariant
            and authored_files_unchanged
            and all(human_checks.values())
        ),
    }


def _run_tdd_refresh_case(
    root: Path,
    *,
    case_id: str,
    initial_language: str,
    rerun_language: str,
    handwritten: bool = False,
) -> dict[str, Any]:
    path = root / case_id
    _write_package(path, "en")
    authored_before = _authored_hashes(path)

    run_readiness_review(path, conversation_language=initial_language)
    output = generate_tests(path)
    if handwritten:
        output.write_text("# Project-owned acceptance tests\n\nDo not replace this file.\n", encoding="utf-8")
    generated_paths = {
        "readiness_report": path / "readiness-review.md",
        "grill_report": path / "grill.md",
        "tdd_report": output,
    }
    before = {name: artifact.read_bytes() for name, artifact in generated_paths.items()}

    run_readiness_review(path, conversation_language=rerun_language)
    generate_tests(path)
    after = {name: artifact.read_bytes() for name, artifact in generated_paths.items()}
    language_changed = initial_language != rerun_language
    expected_changes = {
        "readiness_report": language_changed,
        "grill_report": language_changed,
        "tdd_report": language_changed and not handwritten,
    }
    artifact_changes = {name: before[name] != after[name] for name in generated_paths}
    changed_as_expected = artifact_changes == expected_changes
    expected_heading = "# TDD 시나리오:" if rerun_language == "ko" else "# TDD Scenarios:"
    heading_matches = handwritten or after["tdd_report"].decode("utf-8").startswith(expected_heading)
    authored_files_unchanged = authored_before == _authored_hashes(path)

    return {
        "id": case_id,
        "initial_language": initial_language,
        "rerun_language": rerun_language,
        "handwritten": handwritten,
        "expected_changes": expected_changes,
        "artifact_changes": artifact_changes,
        "changed_as_expected": changed_as_expected,
        "heading_matches": heading_matches,
        "authored_files_unchanged": authored_files_unchanged,
        "passed": changed_as_expected and heading_matches and authored_files_unchanged,
    }


def build_report_language_benchmark(root: Path) -> dict[str, Any]:
    resolution_rows = [_run_resolution_scenario(root, scenario) for scenario in REPORT_LANGUAGE_SCENARIOS]
    refresh_rows = [
        _run_tdd_refresh_case(
            root,
            case_id="language_only_rerun_after_english_output",
            initial_language="en",
            rerun_language="ko",
        ),
        _run_tdd_refresh_case(
            root,
            case_id="language_only_rerun_after_korean_output",
            initial_language="ko",
            rerun_language="en",
        ),
        _run_tdd_refresh_case(
            root,
            case_id="same_language_rerun",
            initial_language="en",
            rerun_language="en",
        ),
        _run_tdd_refresh_case(
            root,
            case_id="handwritten_tdd_language_rerun",
            initial_language="en",
            rerun_language="ko",
            handwritten=True,
        ),
    ]
    expected_legacy = {"code": "en", "source": "fallback", "fallback_used": True}
    legacy_resolution = report_language_from_payload({"readiness": {"status": "ready"}}).as_dict()
    legacy_row = {
        "id": "legacy_json_without_report_language",
        "expected_resolution": expected_legacy,
        "actual_resolution": legacy_resolution,
        "passed": legacy_resolution == expected_legacy,
    }
    all_rows = [*resolution_rows, *refresh_rows, legacy_row]
    return {
        "schema": REPORT_LANGUAGE_BENCHMARK_SCHEMA,
        "scenario_count": len(all_rows),
        "resolution_rows": resolution_rows,
        "artifact_refresh_rows": refresh_rows,
        "legacy_rows": [legacy_row],
        "summary": {
            "passed": sum(1 for row in all_rows if row["passed"]),
            "failed": sum(1 for row in all_rows if not row["passed"]),
            "all_passed": all(row["passed"] for row in all_rows),
        },
    }

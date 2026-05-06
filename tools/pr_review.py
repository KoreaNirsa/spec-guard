from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.llm_client import LLMConfigError, LLMRequestError, build_llm_client
from tools.post_run import readiness_report_stale_reason


COMMENT_MARKER_PREFIX = "specguard-pr-review"
REVIEW_SYSTEM = "\n".join([
    "You are SpecGuard PR Reviewer.",
    "Review the PR diff only for conformance to the approved SpecGuard spec package.",
    "Focus on spec conformance, security, reliability, API contracts, data ownership, testability, and operational risk.",
    "Prioritize concrete spec-to-code mismatches over style comments.",
    "Every finding should cite spec evidence and implementation evidence when possible.",
    "Use severities: blocker, major, minor, advisory.",
    "Say when evidence is insufficient instead of guessing.",
    "Do not request broad rewrites, speculative best-practice changes, or unrelated suggestions.",
    "Return Markdown with sections: Coverage Summary, Findings, Insufficient Evidence, Reviewed Artifacts.",
])


@dataclass(frozen=True)
class ReviewContext:
    spec_packages: list[Path]
    artifacts: dict[str, str]
    diff_text: str


@dataclass(frozen=True)
class ReviewResult:
    status: str
    body: str
    exit_code: int


def credentials_available(env: Mapping[str, str]) -> bool:
    return bool(
        env.get("OPENAI_API_KEY")
        or env.get("SPECGUARD_OPENAI_API_KEY")
        or env.get("SPECGUARD_PR_REVIEW_COMMAND")
    )


def discover_spec_packages(spec_root: Path, diff_text: str, explicit: str | None = None) -> list[Path]:
    if explicit:
        return [Path(item.strip()) for item in explicit.split(",") if item.strip()]

    packages: set[Path] = set()
    for path_text in _diff_paths(diff_text):
        path = Path(path_text)
        parts = path.parts
        if len(parts) >= 2 and parts[0] == spec_root.name:
            candidate = spec_root / parts[1]
            if (candidate / "spec.md").exists():
                packages.add(candidate)
    return sorted(packages)


def readiness_blockers(spec_packages: list[Path]) -> list[str]:
    blockers: list[str] = []
    for package in spec_packages:
        report_path = package / "readiness-review.json"
        if not report_path.exists():
            blockers.append(f"{package}: missing readiness-review.json")
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append(f"{package}: unreadable readiness-review.json ({exc})")
            continue
        readiness = report.get("readiness", {}) if isinstance(report, dict) else {}
        if report.get("blocked") or not isinstance(readiness, dict) or not readiness.get("implementation_ready"):
            blockers.append(f"{package}: SpecGuard readiness is NOT READY")
        stale_reason = readiness_report_stale_reason(package)
        if stale_reason:
            blockers.append(f"{package}: {stale_reason}")
    return blockers


def build_review_context(spec_packages: list[Path], diff_file: Path, *, max_diff_chars: int = 60000) -> ReviewContext:
    artifacts: dict[str, str] = {}
    for package in spec_packages:
        for relative in (
            "discovery.md",
            "spec.md",
            "technical-design.md",
            "readiness-review.json",
            "implementation-output.md",
        ):
            path = package / relative
            if path.exists():
                artifacts[str(path).replace("\\", "/")] = _compact(path.read_text(encoding="utf-8"), 12000)
        for folder in ("tests", "contracts"):
            root = package / folder
            if root.exists():
                for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
                    artifacts[str(path).replace("\\", "/")] = _compact(path.read_text(encoding="utf-8"), 8000)
    diff_text = _compact(diff_file.read_text(encoding="utf-8"), max_diff_chars)
    return ReviewContext(spec_packages=spec_packages, artifacts=artifacts, diff_text=diff_text)


def render_prompt(context: ReviewContext) -> str:
    artifact_text = "\n\n".join(
        f"# Artifact: {path}\n\n{content}" for path, content in sorted(context.artifacts.items())
    )
    return "\n\n".join([
        REVIEW_SYSTEM,
        "# Review Task",
        "Compare the approved SpecGuard artifacts to the PR diff. Identify missing implementation evidence, contradictions, unapproved scope, contract mismatches, security/auth gaps, data ownership gaps, migration risks, and missing tests.",
        "For each finding, provide: severity, spec evidence, implementation evidence, impact, and recommended spec-aligned fix.",
        "Use this coverage row shape when possible: Requirement -> implementation evidence -> tests/contracts evidence -> status.",
        "# Approved SpecGuard Artifacts",
        artifact_text or "No artifacts were selected.",
        "# PR Diff",
        context.diff_text,
    ])


def render_comment(
    *,
    pr_number: str,
    head_sha: str,
    mode: str,
    status: str,
    message: str,
    reviewed_packages: list[Path],
) -> str:
    marker = f"<!-- {COMMENT_MARKER_PREFIX}:{pr_number}:{head_sha} -->"
    packages = ", ".join(str(package).replace("\\", "/") for package in reviewed_packages) or "None"
    return "\n".join([
        marker,
        "# SpecGuard PR Reviewer",
        "",
        "This automated advisory review was generated by SpecGuard using Codex-compatible review rules against the approved spec package and PR diff.",
        "",
        f"- Review mode: {mode}",
        f"- Status: {status}",
        f"- Head SHA: `{head_sha}`",
        f"- Reviewed spec package(s): {packages}",
        "",
        message.strip(),
        "",
    ])


def run_review(args: argparse.Namespace, env: Mapping[str, str] = os.environ) -> ReviewResult:
    mode = args.mode
    if not credentials_available(env):
        body = render_comment(
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            mode=mode,
            status="skipped",
            message="Skipped before context assembly because no Codex/OpenAI review credential was available. Configure `SPECGUARD_OPENAI_API_KEY` or `SPECGUARD_PR_REVIEW_COMMAND` for advisory review.",
            reviewed_packages=[],
        )
        return ReviewResult("skipped", body, 0 if mode == "advisory" else 1)

    diff_text = args.diff_file.read_text(encoding="utf-8")
    spec_packages = discover_spec_packages(args.spec_root, diff_text, explicit=args.spec_paths)
    if not spec_packages:
        body = render_comment(
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            mode=mode,
            status="skipped",
            message="No relevant SpecGuard spec package was discovered from the PR diff. Set `SPECGUARD_REVIEW_SPEC_PATHS` to review an implementation-only PR against an approved package.",
            reviewed_packages=[],
        )
        return ReviewResult("skipped", body, 0)

    blockers = readiness_blockers(spec_packages)
    if blockers:
        body = render_comment(
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            mode=mode,
            status="blocked",
            message="Codex was not invoked because SpecGuard readiness is not approved:\n\n" + "\n".join(f"- {blocker}" for blocker in blockers),
            reviewed_packages=spec_packages,
        )
        return ReviewResult("blocked", body, 0 if mode == "advisory" else 1)

    context = build_review_context(spec_packages, args.diff_file)
    prompt = render_prompt(context)
    if args.prompt_file:
        args.prompt_file.write_text(prompt, encoding="utf-8")

    try:
        review_text = invoke_reviewer(prompt, env=env, model=args.model)
    except (LLMConfigError, LLMRequestError, subprocess.SubprocessError, OSError) as exc:
        body = render_comment(
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            mode=mode,
            status="skipped" if mode == "advisory" else "failed",
            message=f"Codex review could not run: {exc}",
            reviewed_packages=spec_packages,
        )
        return ReviewResult("skipped", body, 0 if mode == "advisory" else 1)

    body = render_comment(
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        mode=mode,
        status="reviewed",
        message=review_text,
        reviewed_packages=spec_packages,
    )
    return ReviewResult("reviewed", body, 0)


def invoke_reviewer(prompt: str, *, env: Mapping[str, str], model: str | None) -> str:
    command = env.get("SPECGUARD_PR_REVIEW_COMMAND")
    timeout = int(env.get("SPECGUARD_PR_REVIEW_TIMEOUT", "180"))
    if command:
        completed = subprocess.run(
            shlex.split(command),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise subprocess.SubprocessError("review command exited non-zero")
        return completed.stdout.strip() or "Review command returned no findings."

    if env.get("SPECGUARD_OPENAI_API_KEY") and not env.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = env["SPECGUARD_OPENAI_API_KEY"]
    client = build_llm_client(Path.cwd(), mode=env.get("SPECGUARD_PR_REVIEW_LLM_MODE", "openai"), model=model)
    return client.generate_text(REVIEW_SYSTEM, prompt, max_output_tokens=4000)


def _diff_paths(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            paths.append(line.removeprefix("+++ b/"))
        elif line.startswith("--- a/"):
            paths.append(line.removeprefix("--- a/"))
    return [path for path in paths if path != "/dev/null"]


def _compact(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    return "\n".join([
        text[:head].rstrip(),
        "",
        f"... omitted {len(text) - max_chars} characters ...",
        "",
        text[-tail:].lstrip(),
    ])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-root", type=Path, default=Path("specs"))
    parser.add_argument("--spec-paths", default=os.getenv("SPECGUARD_REVIEW_SPEC_PATHS"))
    parser.add_argument("--diff-file", type=Path, required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--mode", choices=["advisory", "enforced"], default=os.getenv("SPECGUARD_PR_REVIEW_MODE", "advisory"))
    parser.add_argument("--model", default=os.getenv("SPECGUARD_PR_REVIEW_MODEL"))
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_review(args)
    args.output_file.write_text(result.body, encoding="utf-8")
    print(f"SpecGuard PR review status: {result.status}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

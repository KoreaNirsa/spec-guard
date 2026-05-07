from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.post_run import (
    apply_spec_revision,
    apply_spec_revision_with_audit,
    blocked_feature_reports,
    feature_readiness_reports,
    generate_spec_revision,
    validate_spec_revision_intent,
)
from tools.result import CheckResult
from tools.runner import run_pipeline
from tools.ux import green, red


def run_strict_e2e_pipeline(
    path: Path,
    llm_client: object,
    *,
    force: bool = False,
    max_iterations: int = 3,
) -> CheckResult:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")

    result = CheckResult("SpecGuard strict e2e pipeline")
    trace: dict[str, Any] = {
        "schema_version": "0.1",
        "max_iterations": max_iterations,
        "attempts": [],
        "regenerations": [],
        "final": {},
    }

    attempt = run_pipeline(path, llm_client=llm_client, force=force, review_mode="initial", strict_verification=True)
    _merge_messages(result, attempt)
    _record_attempt(trace, path, 0, "initial", attempt)
    if attempt.ok:
        result.add_info(green("[READY] Strict E2E reached READY after the initial SpecGuard Review."))
        _finish_trace(path, trace, status="ready", iterations=0)
        return result

    for iteration in range(1, max_iterations + 1):
        blocked_reports = blocked_feature_reports(path)
        if not blocked_reports:
            result.add_error(
                "Strict E2E stopped because the pipeline failed outside SpecGuard Review; no readiness findings were available for regeneration."
            )
            result.add_next_step("Fix the non-readiness blocker, then rerun strict E2E.")
            _finish_trace(path, trace, status="failed_non_readiness", iterations=iteration - 1)
            return result

        for feature_dir, report in blocked_reports:
            revised_spec = generate_spec_revision(feature_dir, llm_client)
            intent_check = validate_spec_revision_intent(feature_dir, revised_spec)
            if not intent_check.ok:
                audit = apply_spec_revision_with_audit(feature_dir, revised_spec)
                trace["regenerations"].append(
                    _regeneration_entry(
                        feature_dir,
                        iteration,
                        report,
                        audit.spec_path,
                        intent_preservation="failed",
                        audit_diff_path=audit.diff_path,
                    )
                )
                _merge_messages(result, intent_check)
                result.add_error(
                    red(
                        f"Strict E2E iteration {iteration}: updated {audit.spec_path} for in-place review, then stopped because intent preservation failed."
                    )
                )
                result.add_next_step(f"Review diff: {audit.diff_path}")
                result.add_next_step("Edit spec.md or adjust Readiness Findings before rerunning strict E2E.")
                _finish_trace(path, trace, status="failed_intent_preservation", iterations=iteration - 1)
                return result
            spec_path = apply_spec_revision(feature_dir, revised_spec)
            trace["regenerations"].append(_regeneration_entry(feature_dir, iteration, report, spec_path))
            result.add_info(
                f"Strict E2E iteration {iteration}: regenerated {spec_path} from {len(report.get('issues', []))} readiness finding(s)."
            )

        attempt = run_pipeline(path, llm_client=llm_client, force=True, review_mode="verification", strict_verification=True)
        _merge_messages(result, attempt)
        _record_attempt(trace, path, iteration, "verification", attempt)
        if attempt.ok:
            result.add_info(green(f"[READY] Strict E2E reached READY after {iteration} verification iteration(s)."))
            _finish_trace(path, trace, status="ready", iterations=iteration)
            return result

    result.add_error(red(f"[NOT READY] Strict E2E failed after {max_iterations} verification iteration(s)."))
    result.add_next_step("Review strict-e2e-trace.json and resolve the remaining Critical or Major readiness findings manually.")
    result.add_next_step("Increase --strict-max-iterations only when the findings are converging and the LLM provider is reliable.")
    _finish_trace(path, trace, status="max_iterations_exhausted", iterations=max_iterations)
    return result


def _merge_messages(target: CheckResult, source: CheckResult) -> None:
    target.messages.extend(source.messages)
    target.next_steps.extend(source.next_steps)


def _record_attempt(trace: dict[str, Any], path: Path, iteration: int, review_mode: str, result: CheckResult) -> None:
    trace["attempts"].append({
        "iteration": iteration,
        "review_mode": review_mode,
        "pipeline_ok": result.ok,
        "features": [_feature_report_entry(feature_dir, report) for feature_dir, report in feature_readiness_reports(path)],
    })
    _write_trace(path, trace)


def _feature_report_entry(feature_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    issues = report.get("issues", [])
    return {
        "feature_dir": str(feature_dir),
        "review_mode": report.get("review_mode"),
        "blocked": bool(report.get("blocked")),
        "readiness": report.get("readiness", {}),
        "summary": report.get("summary", {}),
        "issues": [
            {
                "severity": issue.get("severity"),
                "title": issue.get("title"),
                "fix": issue.get("fix"),
            }
            for issue in issues
            if isinstance(issue, dict)
        ],
    }


def _regeneration_entry(
    feature_dir: Path,
    iteration: int,
    report: dict[str, Any],
    spec_path: Path,
    *,
    intent_preservation: str = "passed",
    audit_diff_path: Path | None = None,
) -> dict[str, Any]:
    entry = {
        "iteration": iteration,
        "feature_dir": str(feature_dir),
        "updated_artifact": str(spec_path),
        "intent_preservation": intent_preservation,
        "source_review_mode": report.get("review_mode"),
        "source_summary": report.get("summary", {}),
        "source_findings": [
            {
                "severity": issue.get("severity"),
                "title": issue.get("title"),
                "fix": issue.get("fix"),
            }
            for issue in report.get("issues", [])
            if isinstance(issue, dict)
        ],
    }
    if audit_diff_path is not None:
        entry["audit_diff"] = str(audit_diff_path)
    return entry


def _finish_trace(path: Path, trace: dict[str, Any], *, status: str, iterations: int) -> None:
    trace["final"] = {
        "status": status,
        "iterations": iterations,
    }
    _write_trace(path, trace)


def _write_trace(path: Path, trace: dict[str, Any]) -> None:
    trace_path = path / "strict-e2e-trace.json"
    trace_path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")

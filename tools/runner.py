from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.artifact_generator import ensure_contract, generate_implementation_output, generate_llm_technical_design, generate_technical_design
from tools.contract_checker import check_contracts
from tools.readiness_engine import run_readiness_review
from tools.llm_client import LLMConfigError, build_llm_client
from tools.progress import progress_activity
from tools.result import CheckResult
from tools.spec_validator import validate_spec_basis, validate_technical_design
from tools.tdd_generator import generate_tests
from tools.ux import green
from tools.verification_checker import check_verification_artifacts


def _feature_dirs(path: Path) -> list[Path]:
    if (path / "spec.md").exists():
        return [path]
    if path.is_dir():
        return sorted({spec.parent for spec in path.rglob("spec.md")})
    return [path]


def _is_stale(output: Path, sources: list[Path], force: bool) -> bool:
    if force or not output.exists():
        return True
    output_mtime = output.stat().st_mtime
    return any(source.exists() and source.stat().st_mtime > output_mtime for source in sources)


def _stage_activity(name: str) -> str:
    return {
        "validation": "validating spec artifacts",
        "technical_design": "preparing technical design",
        "technical_validation": "validating technical design",
        "readiness_review": "running SpecGuard Review",
        "tests": "building test scenarios",
        "verification": "checking verification artifacts",
        "contract_generation": "building contract scaffold",
        "contract_validation": "validating contracts",
        "implementation_handoff": "building implementation handoff",
    }.get(name, name.replace("_", " "))


def _time_stage(timings: dict[str, int], name: str, operation, *, activity: str | None = None):
    started = time.perf_counter()
    try:
        with progress_activity(activity or _stage_activity(name)):
            return operation()
    finally:
        timings[name] = int((time.perf_counter() - started) * 1000)


def _record_timings(result: CheckResult, feature_dir: Path, timings: dict[str, int]) -> None:
    total = sum(timings.values())
    timings["total"] = total
    for stage, elapsed_ms in timings.items():
        result.details[f"{feature_dir.name}.{stage}_ms"] = elapsed_ms

    rendered = ", ".join(f"{stage}={elapsed_ms}ms" for stage, elapsed_ms in timings.items())
    result.add_info(f"Performance timings for {feature_dir}: {rendered}")


def run_pipeline(
    path: Path,
    llm_client: object | None = None,
    force: bool = False,
    review_mode: str = "initial",
    strict_verification: bool = False,
    refresh_technical_design: bool | None = None,
) -> CheckResult:
    result = CheckResult("SpecGuard pipeline")
    feature_dirs = _feature_dirs(path)
    if not feature_dirs:
        result.add_error(f"No feature specs found in: {path}")
        result.add_next_step("Run discovery first: specguard init <feature-name>")
        return result

    for feature_dir in feature_dirs:
        timings: dict[str, int] = {}
        validation = _time_stage(timings, "validation", lambda: validate_spec_basis(feature_dir))
        result.messages.extend(validation.messages)
        result.next_steps.extend(validation.next_steps)
        if not validation.ok:
            result.ok = False
            result.add_next_step("Fix discovery.md or spec.md before running the pipeline again.")
            _record_timings(result, feature_dir, timings)
            continue

        discovery_path = feature_dir / "discovery.md"
        spec_path = feature_dir / "spec.md"
        technical_design_path = feature_dir / "technical-design.md"
        test_path = feature_dir / "tests" / f"{feature_dir.name}.test.md"
        contract_path = feature_dir / "contracts" / "openapi.yaml"

        refresh_design = (
            _is_stale(technical_design_path, [discovery_path, spec_path], force)
            if refresh_technical_design is None
            else refresh_technical_design or not technical_design_path.exists()
        )
        if llm_client is None:
            technical_design = _time_stage(
                timings,
                "technical_design",
                lambda: generate_technical_design(feature_dir, force=refresh_design),
            )
        else:
            technical_design = _time_stage(
                timings,
                "technical_design",
                lambda: generate_llm_technical_design(feature_dir, llm_client, force=refresh_design),
            )
        action = "Generated" if technical_design.created else "Reused"
        mode = " LLM" if llm_client is not None and technical_design.created else ""
        result.add_info(f"{action}{mode} technical design: {technical_design.path}")

        technical_validation = _time_stage(timings, "technical_validation", lambda: validate_technical_design(feature_dir))
        result.messages.extend(technical_validation.messages)
        result.next_steps.extend(technical_validation.next_steps)
        if not technical_validation.ok:
            result.ok = False
            result.add_next_step(f"Fix technical design: {technical_design.path}")
            _record_timings(result, feature_dir, timings)
            continue

        review = _time_stage(
            timings,
            "readiness_review",
            lambda: run_readiness_review(feature_dir, llm_client=llm_client, review_mode=review_mode),
        )
        result.messages.extend(review.messages)
        result.next_steps.extend(review.next_steps)
        if not review.ok:
            result.ok = False
            _record_timings(result, feature_dir, timings)
            continue

        refresh_tests = _is_stale(test_path, [spec_path, technical_design_path], force)
        test_output = _time_stage(timings, "tests", lambda: generate_tests(feature_dir, force=refresh_tests))
        result.add_info(f"TDD scenarios ready: {test_output}")

        if strict_verification:
            verification = _time_stage(timings, "verification", lambda: check_verification_artifacts(feature_dir))
            result.messages.extend(verification.messages)
            result.next_steps.extend(verification.next_steps)
            if not verification.ok:
                result.ok = False
                _record_timings(result, feature_dir, timings)
                continue

        refresh_contract = _is_stale(contract_path, [spec_path], force)
        contract = _time_stage(timings, "contract_generation", lambda: ensure_contract(feature_dir, force=refresh_contract))
        contract_action = "Generated" if contract.created else "Reused"
        result.add_info(f"{contract_action} contract scaffold: {contract.path}")

        contracts = _time_stage(timings, "contract_validation", lambda: check_contracts(feature_dir))
        result.messages.extend(contracts.messages)
        result.next_steps.extend(contracts.next_steps)
        if not contracts.ok:
            result.ok = False
            result.add_next_step(f"Fix contract files under: {feature_dir / 'contracts'}")
            _record_timings(result, feature_dir, timings)
            continue

        implementation_output = _time_stage(timings, "implementation_handoff", lambda: generate_implementation_output(feature_dir))
        output_action = "Generated" if implementation_output.created else "Reused"
        result.add_info(f"{output_action} implementation handoff guide: {implementation_output.path}")
        result.add_info(green("External AI implementation handoff ready. SpecGuard stops here and does not invoke Codex or Claude Code as an internal pipeline stage."))
        result.add_next_step(f"Hand this approved guide to an external coding agent: {implementation_output.path}")
        result.add_next_step("Put application code under develop/<stack>/ when implementation happens outside SpecGuard.")
        _record_timings(result, feature_dir, timings)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="specs")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="Use local deterministic generators and heuristic SpecGuard Review")
    parser.add_argument("--llm-mode", choices=["codex", "openai"], help="Override the configured LLM provider mode")
    parser.add_argument("--llm-model", help="Override the configured LLM model")
    args = parser.parse_args()

    llm_client = None
    if not args.no_llm:
        try:
            llm_client = build_llm_client(Path.cwd(), mode=args.llm_mode, model=args.llm_model)
        except LLMConfigError as exc:
            result = CheckResult("SpecGuard pipeline")
            result.add_error(f"LLM provider is required by default: {exc}")
            result.add_next_step("Configure a provider: specguard auth setup")
            result.add_next_step("Use --no-llm only for local heuristic checks or CI examples.")
            result.print()
            return 1

    result = run_pipeline(Path(args.path), llm_client=llm_client, force=args.force)
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

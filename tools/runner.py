from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.artifact_generator import ensure_contract, generate_implementation_output, generate_llm_technical_design, generate_technical_design
from tools.contract_checker import check_contracts
from tools.readiness_engine import run_readiness_review
from tools.llm_client import LLMConfigError, build_llm_client
from tools.result import CheckResult
from tools.spec_validator import validate_spec_basis, validate_technical_design
from tools.tdd_generator import generate_tests
from tools.ux import green


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


def run_pipeline(path: Path, llm_client: object | None = None, force: bool = False, review_mode: str = "initial") -> CheckResult:
    result = CheckResult("SpecGuard pipeline")
    feature_dirs = _feature_dirs(path)
    if not feature_dirs:
        result.add_error(f"No feature specs found in: {path}")
        result.add_next_step("Run discovery first: python -m cli.specguard init <feature-name>")
        return result

    for feature_dir in feature_dirs:
        validation = validate_spec_basis(feature_dir)
        result.messages.extend(validation.messages)
        result.next_steps.extend(validation.next_steps)
        if not validation.ok:
            result.ok = False
            result.add_next_step("Fix discovery.md or spec.md before running the pipeline again.")
            continue

        discovery_path = feature_dir / "discovery.md"
        spec_path = feature_dir / "spec.md"
        technical_design_path = feature_dir / "technical-design.md"
        test_path = feature_dir / "tests" / f"{feature_dir.name}.test.md"
        contract_path = feature_dir / "contracts" / "openapi.yaml"

        refresh_design = _is_stale(technical_design_path, [discovery_path, spec_path], force)
        if llm_client is None:
            technical_design = generate_technical_design(feature_dir, force=refresh_design)
        else:
            technical_design = generate_llm_technical_design(feature_dir, llm_client, force=refresh_design)
        action = "Generated" if technical_design.created else "Reused"
        mode = " LLM" if llm_client is not None and technical_design.created else ""
        result.add_info(f"{action}{mode} technical design: {technical_design.path}")

        technical_validation = validate_technical_design(feature_dir)
        result.messages.extend(technical_validation.messages)
        result.next_steps.extend(technical_validation.next_steps)
        if not technical_validation.ok:
            result.ok = False
            result.add_next_step(f"Fix technical design: {technical_design.path}")
            continue

        review = run_readiness_review(feature_dir, llm_client=llm_client, review_mode=review_mode)
        result.messages.extend(review.messages)
        result.next_steps.extend(review.next_steps)
        if not review.ok:
            result.ok = False
            continue

        refresh_tests = _is_stale(test_path, [spec_path, technical_design_path], force)
        test_output = generate_tests(feature_dir, force=refresh_tests)
        result.add_info(f"TDD scenarios ready: {test_output}")

        refresh_contract = _is_stale(contract_path, [spec_path], force)
        contract = ensure_contract(feature_dir, force=refresh_contract)
        contract_action = "Generated" if contract.created else "Reused"
        result.add_info(f"{contract_action} contract scaffold: {contract.path}")

        contracts = check_contracts(feature_dir)
        result.messages.extend(contracts.messages)
        result.next_steps.extend(contracts.next_steps)
        if not contracts.ok:
            result.ok = False
            result.add_next_step(f"Fix contract files under: {feature_dir / 'contracts'}")
            continue

        implementation_output = generate_implementation_output(feature_dir)
        output_action = "Generated" if implementation_output.created else "Reused"
        result.add_info(f"{output_action} implementation handoff guide: {implementation_output.path}")
        result.add_info(green("External AI implementation handoff ready. SpecGuard stops here and does not invoke Codex or Claude Code as an internal pipeline stage."))
        result.add_next_step(f"Hand this approved guide to an external coding agent: {implementation_output.path}")
        result.add_next_step("Put application code under develop/<stack>/ when implementation happens outside SpecGuard.")

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
            result.add_next_step("Configure a provider: python -m cli.specguard auth setup")
            result.add_next_step("Use --no-llm only for local heuristic checks or CI examples.")
            result.print()
            return 1

    result = run_pipeline(Path(args.path), llm_client=llm_client, force=args.force)
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

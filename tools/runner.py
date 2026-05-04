from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.artifact_generator import ensure_contract, generate_implementation_output, generate_technical_design
from tools.contract_checker import check_contracts
from tools.grill_engine import run_grill
from tools.result import CheckResult
from tools.spec_validator import validate_spec_basis, validate_technical_design
from tools.tdd_generator import generate_tests


def _feature_dirs(path: Path) -> list[Path]:
    if (path / "spec.md").exists():
        return [path]
    if path.is_dir():
        return sorted({spec.parent for spec in path.rglob("spec.md")})
    return [path]


def run_pipeline(path: Path) -> CheckResult:
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

        technical_design = generate_technical_design(feature_dir)
        action = "Generated" if technical_design.created else "Reused"
        result.add_info(f"{action} technical design: {technical_design.path}")

        technical_validation = validate_technical_design(feature_dir)
        result.messages.extend(technical_validation.messages)
        result.next_steps.extend(technical_validation.next_steps)
        if not technical_validation.ok:
            result.ok = False
            result.add_next_step(f"Fix technical design: {technical_design.path}")
            continue

        grill = run_grill(feature_dir)
        result.messages.extend(grill.messages)
        result.next_steps.extend(grill.next_steps)
        if not grill.ok:
            result.ok = False
            continue

        test_output = generate_tests(feature_dir)
        result.add_info(f"TDD scenarios ready: {test_output}")

        contract = ensure_contract(feature_dir)
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
        result.add_info(f"{output_action} implementation output guide: {implementation_output.path}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="specs")
    args = parser.parse_args()
    result = run_pipeline(Path(args.path))
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.contract_checker import check_contracts
from tools.grill_engine import run_grill
from tools.result import CheckResult
from tools.spec_validator import validate_feature
from tools.tdd_generator import generate_tests


def _feature_dirs(path: Path) -> list[Path]:
    if path.name == "specs" or path.is_dir() and not (path / "spec.md").exists():
        return sorted([child for child in path.iterdir() if child.is_dir()])
    return [path]


def run_pipeline(path: Path) -> CheckResult:
    result = CheckResult("SpecGuard pipeline")
    validation = validate_feature(path)
    result.messages.extend(validation.messages)
    if not validation.ok:
        result.ok = False
        return result

    for feature_dir in _feature_dirs(path):
        grill = run_grill(feature_dir)
        result.messages.extend(grill.messages)
        if not grill.ok:
            result.ok = False

        test_output = generate_tests(feature_dir)
        result.add_info(f"Generated TDD scenarios: {test_output}")

        contracts = check_contracts(feature_dir)
        result.messages.extend(contracts.messages)
        if not contracts.ok:
            result.ok = False

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

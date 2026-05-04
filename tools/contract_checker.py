from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.result import CheckResult


def check_contracts(path: Path) -> CheckResult:
    result = CheckResult("Contract validation")
    contracts_dir = path / "contracts"
    if not contracts_dir.exists():
        result.add_info(f"No contracts directory found: {contracts_dir}")
        return result

    contract_files = list(contracts_dir.glob("*.yaml")) + list(contracts_dir.glob("*.yml")) + list(contracts_dir.glob("*.json"))
    if not contract_files:
        result.add_info(f"No contract files found in: {contracts_dir}")
        return result

    for contract in contract_files:
        if contract.stat().st_size == 0:
            result.add_error(f"Contract file is empty: {contract}")
        else:
            result.add_info(f"Found contract: {contract}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="specs")
    args = parser.parse_args()
    result = check_contracts(Path(args.path))
    result.print()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

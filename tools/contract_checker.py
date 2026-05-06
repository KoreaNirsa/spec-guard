from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.result import CheckResult


def _read_yaml_like(path: Path) -> dict[str, object]:
    try:
        import yaml
    except ImportError:
        yaml = None

    content = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(content)
    elif yaml is not None:
        data = yaml.safe_load(content)
    else:
        data = _minimal_yaml(content)

    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    return data


def _minimal_yaml(content: str) -> dict[str, object]:
    data: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, data)]

    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if ":" not in raw_line:
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, value = raw_line.strip().split(":", 1)
        key = key.strip().strip('"')
        value = value.strip().strip('"')

        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if value:
            parent[key] = _minimal_yaml_value(value)
        else:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
    return data


def _minimal_yaml_value(value: str) -> object:
    if value == "{}":
        return {}
    return value


def _validate_openapi(contract: Path, data: dict[str, object], result: CheckResult) -> None:
    if "openapi" not in data:
        result.add_error(f"{contract} must define openapi version")

    info = data.get("info")
    if not isinstance(info, dict):
        result.add_error(f"{contract} must define info.title and info.version")
    else:
        if not info.get("title"):
            result.add_error(f"{contract} must define info.title")
        if not info.get("version"):
            result.add_error(f"{contract} must define info.version")

    paths = data.get("paths")
    if not isinstance(paths, dict):
        result.add_error(f"{contract} must define paths")
        return

    for path_name, path_item in paths.items():
        if path_name == "{}":
            continue
        if not isinstance(path_item, dict):
            result.add_error(f"{contract} path must be an object: {path_name}")
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict) or not isinstance(operation.get("responses"), dict):
                result.add_error(f"{contract} operation must define responses: {method.upper()} {path_name}")


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
            continue

        try:
            data = _read_yaml_like(contract)
            _validate_openapi(contract, data, result)
            result.add_info(f"Validated contract: {contract}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result.add_error(f"Invalid contract file: {contract} ({exc})")
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

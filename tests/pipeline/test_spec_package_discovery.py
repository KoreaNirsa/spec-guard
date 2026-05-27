from __future__ import annotations

from pathlib import Path

from tools.spec_packages import discover_spec_packages, resolve_spec_packages


def write_package(base: Path, name: str = "billing-export") -> Path:
    package = base / "specs" / name
    package.mkdir(parents=True)
    package.joinpath("spec.md").write_text("# Spec\n", encoding="utf-8")
    return package


def test_discovers_root_specs_package(tmp_path: Path) -> None:
    package = write_package(tmp_path)

    assert discover_spec_packages(tmp_path) == [package]


def test_discovers_nested_specs_package(tmp_path: Path) -> None:
    package = write_package(tmp_path / "services" / "billing")

    assert discover_spec_packages(tmp_path) == [package]


def test_multiple_specs_packages_require_explicit_resolution(tmp_path: Path) -> None:
    root_package = write_package(tmp_path, "root-feature")
    nested_package = write_package(tmp_path / "services" / "billing", "nested-feature")

    resolution = resolve_spec_packages(tmp_path)

    assert resolution.ambiguous
    assert resolution.packages == (root_package, nested_package)


def test_discovery_excludes_hidden_dependency_build_and_generated_dirs(tmp_path: Path) -> None:
    visible = write_package(tmp_path / "services" / "billing", "visible")
    for excluded in (".hidden", "node_modules", "build", "generated"):
        write_package(tmp_path / excluded, "ignored")

    assert discover_spec_packages(tmp_path) == [visible]

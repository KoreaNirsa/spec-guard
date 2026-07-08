from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tomllib
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def test_built_wheel_installs_specguard_console_script(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"

    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(dist_dir),
        ],
        cwd=ROOT,
    )

    wheels = sorted(dist_dir.glob(f"spec_guard-{PACKAGE_VERSION}-py3-none-any.whl"))
    assert len(wheels) == 1
    assert (dist_dir / f"spec_guard-{PACKAGE_VERSION}.tar.gz").exists()

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    python = _venv_python(venv_dir)
    specguard = _venv_script(venv_dir, "specguard")

    _run([str(python), "-m", "pip", "install", str(wheels[0])], cwd=tmp_path)

    help_result = _run([str(specguard), "--help"], cwd=tmp_path)
    assert "SpecGuard refines specs into validated implementation-ready artifacts." in help_result.stdout

    auth_result = _run([str(specguard), "auth", "status"], cwd=tmp_path, check=False)
    assert auth_result.returncode == 1
    assert "No LLM provider configured." in auth_result.stdout

    llm_init_result = _run(
        [str(specguard), "init", "pip-smoke", "--non-interactive", "--force"],
        cwd=tmp_path,
        check=False,
    )
    assert llm_init_result.returncode == 1
    assert "No LLM provider is configured." in llm_init_result.stdout

    init_result = _run(
        [str(specguard), "init", "pip-smoke", "--non-interactive", "--force", "--no-llm"],
        cwd=tmp_path,
    )
    assert init_result.returncode == 0
    assert (tmp_path / "specs" / "pip-smoke" / "spec.md").exists()
    assert (tmp_path / ".github" / "workflows" / "specguard-readiness-gate.yml").exists()
    assert "SpecGuard Readiness Gate workflow" in init_result.stdout

    copy_without_force = _run(
        [str(specguard), "example", "copy", "pip-smoke"],
        cwd=tmp_path,
        check=False,
    )
    assert copy_without_force.returncode == 1
    assert "would overwrite existing files" in copy_without_force.stdout

    copy_result = _run(
        [str(specguard), "example", "copy", "pip-smoke", "--force"],
        cwd=tmp_path,
    )
    assert copy_result.returncode == 0
    assert "Copied authored example specs" in copy_result.stdout
    assert (tmp_path / "specs" / "pip-smoke" / "checklists" / "spec-readiness.md").exists()
    assert (tmp_path / "specs" / "pip-smoke" / "contracts" / "openapi.yaml").exists()
    assert (tmp_path / "specs" / "pip-smoke" / "tests" / "team-invite.test.md").exists()
    spec_text = (tmp_path / "specs" / "pip-smoke" / "spec.md").read_text(encoding="utf-8")
    assert "# Spec: Todo Privacy API" in spec_text
    assert "The server does not need to check which user created the todo." in spec_text

    run_result = _run(
        [str(specguard), "run", "specs/pip-smoke", "--no-llm", "--no-follow-up"],
        cwd=tmp_path,
        check=False,
    )
    assert run_result.returncode == 1
    assert "[FAIL] SpecGuard pipeline" in run_result.stdout
    assert "[NOT READY]" in run_result.stdout
    assert "Todo ownership boundary is unclear" in run_result.stdout
    assert not (tmp_path / "specs" / "pip-smoke" / "implementation-output.md").exists()


def test_package_metadata_supports_future_uvx_from_invocation() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "spec-guard"
    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert pyproject["project"]["scripts"]["specguard"] == "cli.specguard:main"

    package_data = pyproject["tool"]["setuptools"]["package-data"]["tools"]
    assert "resources/example/*.md" in package_data
    assert "resources/example/checklists/*.md" in package_data
    assert "resources/example/contracts/*.yaml" in package_data
    assert "resources/example/tests/*.md" in package_data
    assert "resources/workflows/*.yml" in package_data

    packages = pyproject["tool"]["setuptools"]["packages"]
    assert "tools.generation" in packages
    assert "tools.resources" in packages
    assert "tools.resources.example" in packages
    assert "tools.resources.example.checklists" in packages
    assert "tools.resources.example.contracts" in packages
    assert "tools.resources.example.tests" in packages
    assert "tools.resources.workflows" in packages


def test_tools_public_import_contracts_remain_available() -> None:
    public_modules = [
        "tools.action_installer",
        "tools.artifact_generator",
        "tools.contract_checker",
        "tools.discovery_engine",
        "tools.grill_loop",
        "tools.llm_client",
        "tools.post_run",
        "tools.pr_readiness_gate",
        "tools.pr_review",
        "tools.progress",
        "tools.readiness_engine",
        "tools.result",
        "tools.runner",
        "tools.spec_driven_ai_benchmark",
        "tools.spec_packages",
        "tools.spec_validator",
        "tools.strict_e2e",
        "tools.tdd_generator",
        "tools.ux",
        "tools.verification_checker",
    ]

    for module in public_modules:
        importlib.import_module(module)

    resource_packages = [
        "tools.resources",
        "tools.resources.example",
        "tools.resources.workflows",
    ]
    for package in resource_packages:
        importlib.import_module(package)


def test_generation_package_imports_match_root_compatibility_wrappers() -> None:
    root_verification = importlib.import_module("tools.verification_checker")
    generation_verification = importlib.import_module("tools.generation.verification_checker")

    assert root_verification.check_verification_artifacts is generation_verification.check_verification_artifacts
    assert root_verification.verification_metadata is generation_verification.verification_metadata

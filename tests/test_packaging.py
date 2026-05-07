from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
    assert (tmp_path / "specs" / "pip-smoke" / "contracts" / "openapi.yaml").exists()
    assert (tmp_path / "specs" / "pip-smoke" / "tests" / "team-invite.test.md").exists()
    assert "Feature Specification: Team Invite" in (
        tmp_path / "specs" / "pip-smoke" / "spec.md"
    ).read_text(encoding="utf-8")

    run_result = _run(
        [str(specguard), "run", "specs/pip-smoke", "--no-llm", "--no-follow-up"],
        cwd=tmp_path,
    )
    assert run_result.returncode == 0
    assert "External AI implementation handoff ready" in run_result.stdout

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "0.2.1"


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

    run_result = _run(
        [str(specguard), "run", "specs/pip-smoke", "--no-llm", "--no-follow-up"],
        cwd=tmp_path,
        check=False,
    )
    assert run_result.returncode == 1
    assert "appears to be a mostly default init draft" in run_result.stdout

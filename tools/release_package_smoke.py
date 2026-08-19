from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _run(command: list[str], *, cwd: Path, expected_returncode: int = 0) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != expected_returncode:
        rendered = subprocess.list2cmdline(command)
        raise RuntimeError(
            f"Command returned {result.returncode}, expected {expected_returncode}: {rendered}\n"
            f"{result.stdout}"
        )
    return result.stdout


def select_distribution(dist_dir: Path, artifact_kind: str) -> Path:
    pattern = "*.whl" if artifact_kind == "wheel" else "*.tar.gz"
    artifacts = sorted(dist_dir.resolve().glob(pattern))
    if len(artifacts) != 1:
        raise ValueError(
            f"Expected exactly one {artifact_kind} in {dist_dir}, found {len(artifacts)}."
        )
    return artifacts[0]


def run_package_smoke(artifact: Path) -> None:
    artifact = artifact.resolve()
    with tempfile.TemporaryDirectory(prefix="specguard-release-smoke-") as temp_dir:
        root = Path(temp_dir)
        venv_dir = root / "venv"
        workspace = root / "release-검증"
        workspace.mkdir()
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = _venv_python(venv_dir)
        specguard = _venv_script(venv_dir, "specguard")

        _run([str(python), "-m", "pip", "install", str(artifact)], cwd=workspace)
        _run(
            [
                str(python),
                "-c",
                (
                    "from importlib import resources; "
                    "import cli.specguard, tools.runner, tools.readiness_engine; "
                    "assert resources.files('tools').joinpath('resources/example/spec.md').is_file(); "
                    "assert resources.files('tools').joinpath("
                    "'resources/workflows/specguard-readiness-gate.yml').is_file()"
                ),
            ],
            cwd=workspace,
        )
        help_output = _run([str(specguard), "--help"], cwd=workspace)
        if "SpecGuard refines specs into validated implementation-ready artifacts." not in help_output:
            raise RuntimeError("Installed CLI help did not contain the expected description.")

        _run([str(specguard), "example", "copy", "release-smoke"], cwd=workspace)
        run_output = _run(
            [
                str(specguard),
                "run",
                "specs/release-smoke",
                "--no-llm",
                "--no-follow-up",
            ],
            cwd=workspace,
            expected_returncode=1,
        )
        if "[NOT READY]" not in run_output:
            raise RuntimeError("Installed example pipeline did not produce the expected readiness result.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test an installed SpecGuard distribution.")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--artifact-kind", choices=("wheel", "sdist"), required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact = select_distribution(args.dist_dir, args.artifact_kind)
    run_package_smoke(artifact)
    print(f"Installed package smoke passed: {artifact.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

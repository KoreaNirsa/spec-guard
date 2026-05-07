from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_specguard(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "cli.specguard", *args],
        cwd=cwd,
        check=check,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_init_installs_readiness_gate_by_default(tmp_path: Path) -> None:
    result = run_specguard(["init", "billing-export", "--non-interactive", "--no-llm"], tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "specguard-readiness-gate.yml"
    assert workflow.exists()
    assert "python -m pip install spec-guard" in workflow.read_text(encoding="utf-8")
    assert "Installed SpecGuard Readiness Gate workflow" in result.stdout
    assert "SpecGuard Readiness Gate` as a required status check" in result.stdout
    assert "specguard actions install-pr-review" in result.stdout


def test_init_no_actions_skips_workflow_install(tmp_path: Path) -> None:
    run_specguard(["init", "billing-export", "--non-interactive", "--no-llm", "--no-actions"], tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "specguard-readiness-gate.yml"
    assert not workflow.exists()


def test_init_keeps_existing_readiness_gate_without_force_actions(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "specguard-readiness-gate.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Custom Gate\n", encoding="utf-8")

    result = run_specguard(["init", "billing-export", "--non-interactive", "--no-llm"], tmp_path)

    assert workflow.read_text(encoding="utf-8") == "name: Custom Gate\n"
    assert "already exists; kept current file" in result.stdout


def test_actions_install_pr_review_outputs_secret_guidance(tmp_path: Path) -> None:
    result = run_specguard(["actions", "install-pr-review"], tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "specguard-pr-review.yml"
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert "python -m pip install spec-guard" in text
    assert "python -m tools.pr_review" in text
    assert "Installed SpecGuard PR Review workflow" in result.stdout
    assert "SPECGUARD_OPENAI_API_KEY=sk-..." in result.stdout
    assert "SPECGUARD_PR_REVIEW_MODEL=gpt-5.4-nano" in result.stdout
    assert "SPECGUARD_REVIEW_SPEC_PATHS=specs/your-feature-name" in result.stdout


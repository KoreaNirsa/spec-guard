from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

from tools.pr_review import build_review_context, render_comment, render_prompt, run_review


def write_ready_spec_package(tmp_path: Path, *, blocked: bool = False) -> Path:
    feature = tmp_path / "specs" / "feature"
    feature.mkdir(parents=True)
    feature.joinpath("spec.md").write_text(
        "# Spec: feature\n\n## Requirements\n\n- The system must save owner-scoped records.\n",
        encoding="utf-8",
    )
    feature.joinpath("technical-design.md").write_text(
        "# Technical Design: feature\n\n## Architecture\n\n- API and service layer.\n",
        encoding="utf-8",
    )
    feature.joinpath("implementation-output.md").write_text("# Implementation Output\n", encoding="utf-8")
    feature.joinpath("readiness-review.json").write_text(
        json.dumps({
            "blocked": blocked,
            "review_mode": "verification",
            "readiness": {
                "implementation_ready": not blocked,
                "status": "ready" if not blocked else "not_ready",
            },
            "summary": {"critical": 0, "major": 1 if blocked else 0, "minor": 0},
            "issues": [{"severity": "Major", "title": "Owner scope missing", "fix": "Clarify ownership."}] if blocked else [],
        }),
        encoding="utf-8",
    )
    return feature


def write_diff(tmp_path: Path, text: str | None = None) -> Path:
    diff = tmp_path / "pr.diff"
    diff.write_text(
        text
        or "\n".join([
            "diff --git a/specs/feature/spec.md b/specs/feature/spec.md",
            "--- a/specs/feature/spec.md",
            "+++ b/specs/feature/spec.md",
            "@@ -1 +1 @@",
            "+changed",
            "",
        ]),
        encoding="utf-8",
    )
    return diff


def review_args(tmp_path: Path, diff_file: Path, *, spec_paths: str | None = None) -> Namespace:
    return Namespace(
        spec_root=tmp_path / "specs",
        spec_paths=spec_paths,
        diff_file=diff_file,
        pr_number="42",
        head_sha="abc123",
        repo="KoreaNirsa/spec-guard",
        mode="advisory",
        model=None,
        output_file=tmp_path / "comment.md",
        prompt_file=None,
    )


def test_pr_review_skips_missing_credentials_before_context(tmp_path: Path) -> None:
    result = run_review(review_args(tmp_path, tmp_path / "missing.diff"), env={})

    assert result.exit_code == 0
    assert result.status == "skipped"
    assert "no Codex/OpenAI review credential" in result.body
    assert "<!-- specguard-pr-review:42:abc123 -->" in result.body


def test_pr_review_blocks_not_ready_specs_without_invoking_codex(tmp_path: Path) -> None:
    write_ready_spec_package(tmp_path, blocked=True)
    diff = write_diff(tmp_path)

    result = run_review(review_args(tmp_path, diff), env={"OPENAI_API_KEY": "test-key"})

    assert result.exit_code == 0
    assert result.status == "blocked"
    assert "Codex was not invoked" in result.body
    assert "SpecGuard readiness is NOT READY" in result.body


def test_pr_review_prompt_uses_specguard_reviewer_persona(tmp_path: Path) -> None:
    feature = write_ready_spec_package(tmp_path)
    diff = write_diff(tmp_path, "diff --git a/develop/app.py b/develop/app.py\n+++ b/develop/app.py\n+pass\n")

    context = build_review_context([feature], diff)
    prompt = render_prompt(context)

    assert "SpecGuard PR Reviewer" in prompt
    assert "Requirement -> implementation evidence -> tests/contracts evidence -> status" in prompt
    assert "Say when evidence is insufficient instead of guessing" in prompt
    assert "specs/feature/spec.md" in prompt.replace("\\", "/")
    assert "develop/app.py" in prompt


def test_pr_review_comment_has_stable_identity_marker(tmp_path: Path) -> None:
    body = render_comment(
        pr_number="42",
        head_sha="abc123",
        mode="advisory",
        status="reviewed",
        message="## Coverage Summary\n\nNo findings.",
        reviewed_packages=[tmp_path / "specs" / "feature"],
    )

    assert body.startswith("<!-- specguard-pr-review:42:abc123 -->")
    assert "# SpecGuard PR Reviewer" in body
    assert "automated advisory review" in body

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _local_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for raw_target in MARKDOWN_LINK_RE.findall(markdown):
        target = raw_target.split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append(target)
    return targets


def test_readme_language_entrypoints_cross_link_and_keep_package_readme_primary() -> None:
    english = _read("README.md")
    korean = _read("README.ko.md")
    pyproject = tomllib.loads(_read("pyproject.toml"))

    assert english.startswith("[English](README.md) | [한국어](README.ko.md)")
    assert korean.startswith("[한국어](README.ko.md) | [English](README.md)")
    assert pyproject["project"]["readme"] == "README.md"


def test_korean_readme_covers_required_overview_and_support_boundaries() -> None:
    korean = _read("README.ko.md")

    required = (
        "pip install spec-guard",
        "specguard run specs/your-feature-name",
        "codex plugin marketplace add KoreaNirsa/spec-guard --ref main",
        "specguard run <package> --no-llm --no-follow-up",
        "English 110",
        "Korean 110",
        "영어 110개와 한국어 110개",
        "전체 CLI 현지화",
        "전체 한국어 프로덕션 지원",
        "Language Support](docs/language-support.md)",
        "Spec-Driven Benchmark](docs/spec-driven-benchmark.md)",
        "Codex Plugin Guide](docs/codex-plugin.md)",
    )

    missing = [item for item in required if item not in korean]
    assert not missing


def test_readme_language_split_keeps_local_links_resolvable() -> None:
    for readme_path in ("README.md", "README.ko.md"):
        markdown = _read(readme_path)
        base = ROOT / readme_path
        missing = [
            target
            for target in _local_markdown_targets(markdown)
            if not (base.parent / target).exists()
        ]

        assert not missing


def test_docs_record_validated_pinned_uvx_path_without_secret_placeholders() -> None:
    readme = _read("README.md")
    setup_flow = _read("docs/setup-to-user-flow.md")
    workflow = _read("docs/workflow.md")
    uvx_plan = _read("docs/uvx-support-plan.md")

    pinned_command = "uvx --from spec-guard==0.4.2 specguard --help"
    assert pinned_command in readme
    assert pinned_command in setup_flow
    assert pinned_command in uvx_plan
    assert "Windows clean-environment smoke passed" in uvx_plan
    assert "macOS and Linux `uvx` shims still need" in uvx_plan

    for doc in (readme, setup_flow, workflow):
        assert "Secret name: SPECGUARD_OPENAI_API_KEY" in doc
        assert "SPECGUARD_OPENAI_API_KEY=sk-" not in doc

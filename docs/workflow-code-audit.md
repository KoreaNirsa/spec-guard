# SpecGuard Workflow Code Audit

This audit records which repository files are part of the supported installed CLI workflow and which legacy files were removed before adding new product surface area.

## Supported User Workflow

The pip-installed user workflow starts at the `specguard` console script declared in `pyproject.toml`.

Supported entrypoints:

- `specguard init <feature>` creates `specs/`, `develop/`, and the default readiness gate workflow.
- `specguard init <feature> --no-actions` skips workflow installation.
- `specguard example copy <feature>` copies the packaged authored example from `tools.resources.example`.
- `specguard run <path>` runs validation, technical design generation, SpecGuard Review, test generation, contract validation, and implementation handoff.
- `specguard auth setup`, `specguard auth status`, and `specguard auth logout` manage local LLM configuration.
- `specguard actions install-readiness-gate` and `specguard actions install-pr-review` copy packaged consumer GitHub Actions workflows from `tools.resources.workflows`.

## Retained Assets

- `tools/resources/example/`: packaged resource used by `specguard example copy` after `pip install spec-guard`.
- `tools/resources/workflows/`: packaged consumer workflow templates used by `specguard init` and `specguard actions`.
- `examples/example/`: repository CI passing example used by `.github/workflows/pipeline.yml`.
- `examples/risk/todo-api/`: repository CI risk example used by `.github/workflows/pipeline.yml`.
- `.github/workflows/pipeline.yml`: SpecGuard repository development CI.
- `.github/workflows/publish-pypi.yml`: release publishing workflow.
- `.github/workflows/specguard-pr-review.yml`: advisory PR review workflow for this repository.
- `tools/spec_driven_ai_benchmark.py` and `docs/spec-driven-benchmark.md`: benchmark harness and published benchmark evidence.

## Removed Legacy Assets

- `example/`: duplicate clone-era authored example. The supported installed workflow now uses `tools/resources/example/`.
- `templates/`: static Markdown/YAML templates that are not read by the CLI. Current artifact generation is implemented in `tools.discovery_engine` and `tools.artifact_generator`.
- `examples/simple-auth/`: stale generated sample with no references from README, docs, tests, CI, package data, or CLI commands.

## Reference Checks

Before removal, the deleted paths had no references from current user-facing docs, tests, CI workflows, package metadata, or CLI modules. The packaged `tools/resources/example/` references in `pyproject.toml` are expected and were retained.

- `git ls-files example templates examples/simple-auth`
- `git grep -n "examples/simple-auth" -- README.md docs tests tools cli .github pyproject.toml`
- `git grep -n "templates/" -- README.md docs tests tools cli .github pyproject.toml`

Installed-wheel behavior remains covered by `tests/test_packaging.py`, including the `specguard` console script, `init`, default readiness workflow installation, `example copy`, and `run`.

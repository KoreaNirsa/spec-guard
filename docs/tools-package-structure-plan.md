# Tools Package Structure Plan

Issue #226 keeps the current `tools/` package usable while documenting a staged path toward a clearer package layout. This plan intentionally avoids moving modules in one step because `tools.*` imports are already part of the CLI, tests, packaged workflows, plugin helper scripts, and benchmark metadata.

## Current Public Contracts

The current root-level modules under `tools/` are public compatibility contracts until a migration issue explicitly replaces them:

- `cli/specguard.py` imports `tools.action_installer`, `tools.discovery_engine`, `tools.grill_loop`, `tools.llm_client`, `tools.post_run`, `tools.progress`, `tools.readiness_engine`, `tools.runner`, `tools.strict_e2e`, and `tools.ux`.
- Tests import root modules including `tools.contract_checker`, `tools.pr_readiness_gate`, `tools.pr_review`, `tools.result`, `tools.spec_driven_ai_benchmark`, `tools.spec_packages`, `tools.spec_validator`, `tools.tdd_generator`, and `tools.verification_checker`.
- Repository and packaged workflow files invoke `python -m tools.pr_readiness_gate` and `python -m tools.pr_review`.
- Benchmark metadata and published benchmark docs record `tools/spec_driven_ai_benchmark.py` as the fixture source.
- The plugin spec report helper imports `tools.post_run.readiness_report_stale_reason`.

The resource package is also a runtime contract:

- `specguard example copy` reads authored example files from `tools.resources.example`.
- `specguard init` and `specguard actions` read workflow templates from `tools.resources.workflows`.
- `pyproject.toml` must continue declaring `tools.resources`, `tools.resources.example`, `tools.resources.example.checklists`, `tools.resources.example.contracts`, `tools.resources.example.tests`, and `tools.resources.workflows`.
- `pyproject.toml` package data must continue including `resources/example/*.md`, `resources/example/checklists/*.md`, `resources/example/contracts/*.yaml`, `resources/example/tests/*.md`, and `resources/workflows/*.yml` under the `tools` package.

## Target Package Shape

Future issues can introduce focused internal packages while keeping the root modules as compatibility wrappers:

| Target package | Candidate modules | Reason |
| --- | --- | --- |
| `tools.generation` | `artifact_generator`, `contract_checker`, `discovery_engine`, `spec_validator`, `tdd_generator`, `verification_checker` | Spec discovery, artifact generation, tests, and validation. |
| `tools.readiness` | `grill_loop`, `post_run`, `readiness_engine`, `strict_e2e`, `pr_readiness_gate` | Readiness review, follow-up, strict gate, and PR gate behavior. |
| `tools.review` | `pr_review` | PR review prompt construction and review posting logic. |
| `tools.cli_support` | `action_installer`, `llm_client`, `progress`, `result`, `runner`, `spec_packages`, `ux` | CLI orchestration, shared result types, package discovery, progress, UX, and LLM configuration support. |
| `tools.benchmarks` | `spec_driven_ai_benchmark` | Benchmark utilities and fixture metadata. |
| `tools.resources` | `resources/example`, `resources/workflows` | Packaged runtime resources. This path should stay stable. |

## Migration Rules

Each future move should be a separate, small issue with compatibility tests:

1. Add the new package path first and update `pyproject.toml` package declarations in the same change.
2. Keep the existing `tools.<module>` file as a compatibility wrapper that re-exports the public API from the new location.
3. For modules used with `python -m tools.<module>`, keep the old module executable and delegate to the new module entrypoint.
4. Preserve documented resource paths and package-data globs for `tools/resources/example/` and `tools/resources/workflows/`.
5. Move internal imports only after old and new import paths are both covered by tests.
6. Update docs and benchmark metadata only when the moved path is no longer a published compatibility promise.
7. Remove compatibility wrappers only in a release-scoped breaking-change issue with migration notes.

## Validation Boundary

Before and after any structure migration, run:

```bash
python -m pytest tests/packaging/test_packaging.py tests/cli/test_cli_help.py tests/pipeline/test_pipeline.py
python -m build
```

For changes touching workflow entrypoints, also run the relevant PR workflow or local command that invokes `python -m tools.pr_readiness_gate` or `python -m tools.pr_review`.

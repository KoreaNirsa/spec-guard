# SpecGuard v0.4.2 Release Notes

Release type: patch

Package version: `0.4.2`

## Summary

SpecGuard v0.4.2 packages the post-v0.4.1 CLI, plugin, documentation, and test
maintenance work. It does not change the `readiness-review.json` schema, make
LLM review the default gate, or refresh the recorded v0.4.1 benchmark artifact.

## Highlights

- Adds nested spec package discovery support for repositories with module-level
  `specs/<feature>/spec.md` layouts.
- Adds the CLI-driven Grill me loop and guided rerun documentation so blocked
  readiness findings can be turned into traceable follow-up decisions.
- Adds human-readable spec report generation for plugin workflows and hardens
  report handling around stale readiness data.
- Improves Codex plugin result summaries, recovery states, and contributor-only
  workflow scenario fixtures.
- Groups tests by workflow area so CLI, pipeline, readiness, PR review, plugin,
  packaging, benchmark, and docs coverage have clearer ownership.

## Changes Since v0.4.1

### CLI And Spec Package Resolution

- Added nested `**/specs/<feature>/spec.md` package discovery while preserving
  root `specs/<feature>/` support.
- Ignored root placeholder specs paths in readiness gate and PR review package
  discovery.
- Removed the duplicated root example package after retaining the packaged
  `tools/resources/example/` workflow.

### Readiness And Follow-up Workflows

- Added the CLI-driven Grill me loop for finding summaries, user decisions,
  patch planning, patch application, and rerun comparison.
- Documented guided rerun behavior and clarified deferred rerun findings.
- Added Korean readiness phrasing variants and paired safe guards without
  refreshing the benchmark artifact.

### Codex Plugin

- Added readiness summary UX and run recovery states for plugin consumers.
- Defined the plugin result summary prompt contract.
- Added contributor-only plugin workflow scenario fixtures.
- Added human-readable spec report generation and hardened report generation
  failure handling.

### Documentation And Test Maintenance

- Added the Korean README entry point while keeping `README.md` as the package
  README.
- Documented `tools/` package migration contracts before future module moves.
- Reorganized tests into workflow-area directories and updated documented test
  commands.

## Compatibility

- Python support remains `>=3.11`.
- The console script remains `specguard`.
- The default local gate remains `specguard run <package> --no-llm --no-follow-up`.
- SpecGuard PR Review remains optional and advisory.
- `readiness-review.json` remains on schema version `0.1`.

## Known Limits

- Korean support remains a deterministic low-mode claim for explicit unsafe
  wording; it is not a full Korean production-support claim.
- CLI output localization is not included in v0.4.2.
- The recorded benchmark artifact remains the v0.4.1 198-case gate-only run.
  The fixture source has expanded since then, but updated benchmark claims must
  wait for a benchmark refresh.
- Human-readable spec reports are plugin workflow artifacts; the stable machine
  contract remains `readiness-review.json`.

## Release Validation

Before tagging v0.4.2, run:

```bash
python -m pytest tests/packaging/test_packaging.py
python -m pytest tests/benchmark/test_benchmark_metadata.py tests/readiness/test_readiness_calibration.py tests/readiness/test_readiness_fixture_drift.py tests/plugin/test_specguard_plugin_workflow.py
python -m pytest
python -m build
git diff --check
```

After merging the release preparation PR, tag from `main`:

```bash
git tag v0.4.2
git push origin v0.4.2
```

The PyPI publish workflow runs on `v*` tags.

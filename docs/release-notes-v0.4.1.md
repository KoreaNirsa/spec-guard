# SpecGuard v0.4.1 Release Notes

Release type: patch

Package version: `0.4.1`

## Summary

SpecGuard v0.4.1 is a stabilization release for the local readiness gate, Korean
gate-only evidence, benchmark traceability, and Codex plugin documentation. It
does not change the `readiness-review.json` schema or make LLM review the
default gate.

## Highlights

- Stabilizes the recorded v0.4.1 English and Korean gate-only benchmark layer.
- Adds readiness coverage and fixture drift checks so benchmark fixture expansion
  is explicit and traceable.
- Tightens readiness heuristics around workspace invite recipient binding,
  audit immutability, background job retry budgets, and critical evidence shape.
- Clarifies Korean support claims as deterministic low-mode coverage for
  explicit unsafe wording, not full CLI localization or full Korean production
  support.
- Documents Codex plugin workflow hardening, PR Review setup boundaries, and the
  planned CLI-driven Grill me loop.

## Changes Since v0.4.0

### Readiness Calibration

- Added coverage matrix generation and audit documentation for readiness fixture
  gaps and benchmark result coverage.
- Added fixture drift guards for duplicate mappings and intentional fixture
  expansion.
- Added a calibration triage protocol for false positives, false negatives,
  evidence quality, fixture gaps, and Korean counterpart gaps.
- Fixed invite recipient-binding false positives and false negatives.
- Improved critical finding evidence shape and source filtering.
- Added and clarified audit and background job readiness fixture pairs.

### Benchmark Evidence

- Refreshed the v0.4.1 gate-only benchmark artifact with 198 evaluated cases:
  99 English and 99 corresponding Korean cases.
- Preserved separate English and Korean metrics in the README and benchmark
  documentation.
- Recorded the current limitation that the fixture source contains 100 English
  and 100 Korean cases, while 2 new ready/reference fixture results remain
  pending until the next benchmark refresh.

### Codex Plugin And Documentation

- Documented the v0.4.x Codex plugin hardening roadmap.
- Documented guided PR Review setup and safe secret-handling boundaries.
- Clarified plugin installation, supported versions, and setup flow.
- Added Korean documentation policy and support boundary documentation.
- Added a design document for the future CLI-driven Grill me loop.

## Compatibility

- Python support remains `>=3.11`.
- The console script remains `specguard`.
- The default local gate remains `specguard run <package> --no-llm --no-follow-up`.
- SpecGuard PR Review remains optional and advisory.
- `readiness-review.json` remains on schema version `0.1`.

## Known Limits

- Korean support is deterministic low-mode coverage for explicit unsafe wording;
  it is not a full Korean production-support claim.
- CLI output localization is not included in v0.4.1.
- The recorded v0.4.1 benchmark artifact evaluates 198 cases, while the current
  fixture source contains 200 selected cases.
- The CLI-driven Grill me loop is design-only in this release.

## Release Validation

Before tagging v0.4.1, run:

```bash
python -m pytest tests/test_packaging.py
python -m pytest tests/test_benchmark_metadata.py tests/test_readiness_calibration.py tests/test_readiness_fixture_drift.py tests/test_specguard_plugin_workflow.py
python -m pytest
git diff --check
```

After merging the release preparation PR, tag from `main`:

```bash
git tag v0.4.1
git push origin v0.4.1
```

The PyPI publish workflow runs on `v*` tags.

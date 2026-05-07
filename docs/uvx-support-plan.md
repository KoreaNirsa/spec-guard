# Future uvx Support Plan

This document tracks future `uvx` execution support without making it part of the current published user workflow before a clean PyPI release test proves it.

## Status

`uvx` support is future-only for now. The supported installation path remains:

```bash
python -m pip install spec-guard
specguard --help
```

Do not add README quickstart wording for `uvx` until the clean-environment test plan below passes against a published release.

## Current Packaging Assessment

Current metadata appears compatible with a future `uvx --from` invocation:

- Distribution name: `spec-guard`
- Console script: `specguard = "cli.specguard:main"`
- Python requirement: `>=3.11`
- Runtime package data includes:
  - `tools/resources/example/*`
  - `tools/resources/workflows/*.yml`
- Runtime dependencies: none outside the Python standard library.

Because the distribution name is `spec-guard` but the executable script is `specguard`, the expected command form is:

```bash
uvx --from spec-guard specguard --help
```

For release-stable validation, pin the published version:

```bash
uvx --from spec-guard==0.2.3 specguard --help
```

Avoid documenting `uvx spec-guard` unless a future release intentionally exposes a `spec-guard` console script or that command form is tested.

## Known Gaps

- The `uvx --from spec-guard specguard` path still needs a clean PyPI test after the target release is published.
- The command must be verified on Windows, macOS, and Linux because console script shims differ by platform.
- Workflow installation must be verified from the ephemeral `uvx` environment, especially `.github/workflows/specguard-readiness-gate.yml` and `.github/workflows/specguard-pr-review.yml`.
- The command must be verified from a temporary application repository, not from the SpecGuard source checkout.
- LLM provider config must continue to resolve under the user's working directory through `.specguard/`, not inside the ephemeral tool environment.

## Clean-Environment Test Plan

Run these from a new temporary directory after publishing the target version to PyPI:

```bash
mkdir specguard-uvx-smoke
cd specguard-uvx-smoke
git init

uvx --from spec-guard==0.2.3 specguard --help
uvx --from spec-guard==0.2.3 specguard init uvx-smoke --non-interactive --no-llm
test -f .github/workflows/specguard-readiness-gate.yml

uvx --from spec-guard==0.2.3 specguard example copy uvx-smoke --force
uvx --from spec-guard==0.2.3 specguard run specs/uvx-smoke --no-llm --no-follow-up
uvx --from spec-guard==0.2.3 specguard actions install-pr-review
test -f .github/workflows/specguard-pr-review.yml
```

On PowerShell, replace the `test -f` checks with:

```powershell
Test-Path .github\workflows\specguard-readiness-gate.yml
Test-Path .github\workflows\specguard-pr-review.yml
```

Expected results:

- `specguard --help` shows the same command surface as the pip-installed CLI.
- `init` writes `specs/`, `develop/`, and the default readiness gate workflow.
- `example copy` reads packaged example resources from the installed distribution.
- `run --no-llm --no-follow-up` completes without requiring local source files.
- `actions install-pr-review` writes the optional PR Review workflow and prints secret setup guidance.

## Local Source Preflight

Before release, this local source smoke can catch packaging metadata regressions, but it is not enough to publish README wording:

```bash
uvx --from . specguard --help
```

## Release Decision

Keep `uvx` out of the v0.2.3 quickstart unless the clean PyPI test passes. If it passes, document the pinned form first:

```bash
uvx --from spec-guard==0.2.3 specguard --help
```

After at least one release validates the command form, consider adding an unpinned convenience example.

# uvx Support Validation

This document records the `uvx --from` execution path for published SpecGuard releases. It keeps the public guidance pinned and conservative so users can distinguish a validated one-off command from the regular installed CLI workflow.

## Status

The Windows clean-environment smoke passed for the published `spec-guard==0.4.2` package on 2026-07-08. The validated pinned command form is:

```bash
uvx --from spec-guard==0.4.2 specguard --help
```

The regular installed workflow remains supported and recommended for repeated project work:

```bash
python -m pip install spec-guard
specguard --help
```

Keep the `uvx` example pinned to a validated published version. Do not document unpinned `uvx --from spec-guard specguard ...` as a quickstart command until a later release explicitly validates that convenience path. Do not document `uvx spec-guard` unless a future release intentionally exposes a `spec-guard` console script and tests that command form.

## Packaging Assessment

The validated command uses the distribution name and console script declared in package metadata:

- Distribution name: `spec-guard`
- Console script: `specguard = "cli.specguard:main"`
- Python requirement: `>=3.11`
- Runtime package data includes:
  - `tools/resources/example/*`
  - `tools/resources/workflows/*.yml`
- Runtime dependencies: none outside the Python standard library.

Because the distribution name is `spec-guard` but the executable script is `specguard`, the supported command shape is:

```bash
uvx --from spec-guard==0.4.2 specguard <command>
```

## Windows Smoke Record

The smoke was run from a temporary application repository outside the SpecGuard source checkout:

```powershell
git init
uvx --from spec-guard==0.4.2 specguard --help
uvx --from spec-guard==0.4.2 specguard init uvx-smoke --non-interactive --no-llm
Test-Path .github\workflows\specguard-readiness-gate.yml
uvx --from spec-guard==0.4.2 specguard example copy uvx-smoke --force
uvx --from spec-guard==0.4.2 specguard run specs\uvx-smoke --no-llm --no-follow-up
uvx --from spec-guard==0.4.2 specguard actions install-pr-review
Test-Path .github\workflows\specguard-pr-review.yml
```

Observed results:

- `specguard --help` exposed the expected CLI commands from the ephemeral `uvx` environment.
- `init` wrote `specs/uvx-smoke`, `develop/`, and `.github/workflows/specguard-readiness-gate.yml` into the temporary application repository.
- `example copy` read packaged example resources from the installed distribution and copied 10 files into `specs/uvx-smoke`.
- `run --no-llm --no-follow-up` completed without local source files. It reported the intentionally vulnerable packaged example as `NOT READY` and wrote `readiness-review.md` plus `readiness-review.json`.
- `actions install-pr-review` wrote `.github/workflows/specguard-pr-review.yml` into the temporary application repository.
- No local `.specguard/` provider config was created by the default no-LLM smoke path.
- The PR Review installer printed setup guidance for the required GitHub Actions secret and optional variables; no actual secret value was read from the environment or printed.

## Remaining Gaps

- macOS and Linux `uvx` shims still need the same clean-environment smoke before docs claim cross-platform `uvx` validation.
- The unpinned convenience form remains intentionally undocumented in quickstarts.
- The `uvx spec-guard` form remains unsupported because the package exposes `specguard`, not `spec-guard`, as its console script.
- A future wheel or source-layout change should rerun this smoke because packaged examples and workflow templates are runtime resources.

## Release Guidance

Public quickstarts may show the pinned published form as an optional one-off smoke path:

```bash
uvx --from spec-guard==0.4.2 specguard --help
```

For repeated project work, prefer `python -m pip install spec-guard` or a project-managed virtual environment so users do not have to repeat the `uvx --from ...` prefix for every command.

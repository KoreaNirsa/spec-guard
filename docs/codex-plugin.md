# Codex Plugin Guide

This guide documents the SpecGuard Codex plugin MVP. The plugin is a Codex workflow wrapper around the existing `specguard` CLI. The CLI is the canonical engine for review, artifact generation, validation, and implementation handoff.

The MVP does not provide a native SpecGuard engine inside Codex, does not expose a full MCP interface, and does not automatically rewrite specs.

Supported versions: Python 3.11, 3.12, or 3.13, and a Codex CLI version that supports `codex plugin marketplace`. This setup has been verified with Codex CLI 0.130.0.

## Install From The SpecGuard Marketplace

The SpecGuard repository exposes a repo-scoped Codex plugin marketplace at:

```text
.agents/plugins/marketplace.json
```

Add it to Codex with:

```bash
codex plugin marketplace add KoreaNirsa/spec-guard --ref main
```

This is a custom repository marketplace, not the official OpenAI Plugin Directory. Official public plugin publishing is outside the MVP scope.

After adding the marketplace:

1. Restart or refresh Codex if the plugin directory does not update immediately.
2. Open the Codex plugin directory.
3. Select the `SpecGuard Plugins` marketplace source.
4. Install the `SpecGuard` plugin.
5. Prepare your target project folder. If you do not have a project yet, create one first:

   ```bash
   mkdir your-codex-project-folder
   cd your-codex-project-folder
   ```

6. Prepare a spec package. To test SpecGuard with the sample package, run:

   ```bash
   specguard example copy specs/your-feature-name --force
   ```

7. Open `your-codex-project-folder` in Codex, then ask it to run SpecGuard on the package:

   ```text
   Run SpecGuard on specs/your-feature-name.
   ```

Installing the plugin does not install the `specguard` CLI. Before using the plugin in a target workspace, confirm:

```bash
specguard --help
```

If that command is unavailable, install SpecGuard first:

```bash
pip install spec-guard
```

From this repository checkout, this fallback is also valid:

```bash
python -m cli.specguard --help
```

## Add The Local Plugin To Codex App

The repository-local plugin bundle lives at:

```text
plugins/specguard/
```

The required plugin manifest is:

```text
plugins/specguard/.codex-plugin/plugin.json
```

To add it from a repository checkout:

1. Install SpecGuard or use a source checkout where the CLI fallback works.
2. Confirm the CLI is available in the target workspace:

   ```bash
   specguard --help
   ```

   From this repository checkout, this fallback is also valid:

   ```bash
   python -m cli.specguard --help
   ```

3. In the Codex app local plugin flow, add the `plugins/specguard/` directory from this checkout.
4. Start a Codex session in the repository that contains the target spec package.
5. Ask Codex to run SpecGuard on a package, for example:

   ```text
   Run SpecGuard on specs/your-feature-name.
   ```

If a Codex workspace uses repo-local marketplace metadata instead of direct local plugin selection, the entry should point to the same plugin directory:

```json
{
  "name": "specguard",
  "source": {
    "source": "local",
    "path": "./plugins/specguard"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Developer Tools"
}
```

The checked-in repo marketplace already provides this entry through `.agents/plugins/marketplace.json`.

## Expected User Flow

1. Create or select a spec package under `specs/<feature>/`.
2. Ask Codex to run the default SpecGuard plugin workflow.
3. The plugin runs:

   ```bash
   specguard run <package> --no-llm --no-follow-up
   ```

4. The plugin reads `readiness-review.json` and `readiness-review.md`.
5. If the package is `NOT_READY`, inspect the findings, manually edit the spec package, and rerun SpecGuard.
6. If the package is `READY` or `READY_WITH_WARNINGS`, use `implementation-output.md` as the implementation handoff when it exists.
7. After implementation, install and use SpecGuard PR Review only when the repository wants the advisory pull request workflow.

## Architecture

The plugin orchestrates the CLI. It must not embed, fork, or reimplement SpecGuard review logic.

- CLI command execution remains the source of truth.
- `readiness-review.json` is the machine-readable result.
- `readiness-review.md` is the human-readable report.
- `implementation-output.md` is the implementation handoff when the gate allows it.
- Terminal output is not the readiness contract.

For stable fields and file-based states, see [Plugin Result Contract](plugin-result-contract.md).

For the suggestion-only spec refinement boundary, see [SpecGuard Codex Plugin: Spec Refinement Safety Boundary](../plugins/specguard/README.md#spec-refinement-safety-boundary).

## Default Gate

The default plugin gate is heuristic SpecGuard Review:

```bash
specguard run <package> --no-llm --no-follow-up
```

This path does not require Codex or OpenAI provider setup. It should be used first unless the user explicitly asks for provider-backed review.

## Optional Detail Review

Codex-backed Detail Review is optional and advisory. It is not the default gate and it does not replace `readiness-review.json`.

Use it only when the user explicitly asks for provider-backed detail review. Before attempting it, check provider setup:

```bash
specguard auth status
```

If no provider is configured, report `missing_provider_for_llm` and tell the user to configure a provider before retrying. Do not pretend Detail Review ran.

When provider setup is available and the user requested Detail Review, use the existing CLI follow-up menu path:

```bash
specguard run <package> --llm --follow-up
```

Then choose the review-only Detail Review action and read `readiness-review-detail.json` plus `readiness-review-detail.md`.

## Validation Scenarios

| Scenario | Plugin action | Expected result |
| --- | --- | --- |
| missing `specguard` CLI | Run `specguard --help`, then source fallback `python -m cli.specguard --help` when in this checkout. | Report `missing_cli` and ask the user to install SpecGuard or run from a source checkout. |
| existing spec package reaches `READY` | Run the default heuristic gate and read structured result files. | Report `READY`, finding counts, report paths, and `implementation-output.md` when present. |
| existing spec package is `NOT_READY` with Critical findings | Read `readiness-review.json` and `readiness-review.md`. | Summarize Critical findings first and provide suggestion-only spec refinement proposals without editing files. |
| `READY_WITH_WARNINGS` handoff guidance | Read structured result files and check handoff availability. | Report warnings, confirm implementation is allowed, and point to `implementation-output.md` when present. |
| optional detail review requested without provider setup | Run `specguard auth status` before detail review. | Report `missing_provider_for_llm`; do not run or claim provider-backed review. |

## Non-Goals

- Do not claim native plugin engine support.
- Do not document full MCP support until it exists.
- Do not document automatic spec rewriting as a supported plugin behavior.
- Do not treat Codex suggestions as implementation input until the user approves and updates the spec.

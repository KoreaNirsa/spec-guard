# CI And PR Gates

Pull request CI includes a stable required-check candidate named `SpecGuard Readiness Gate`. It inspects changed packages under `specs/`, fails when a changed package is NOT_READY, and fails when source artifacts are stale relative to `readiness-review.json`.

The supported-Python test matrix is summarized by a fixed `Tests` check. Keep this aggregate check name stable when changing the matrix job names so branch protection rules continue to match it.

`specguard init <feature>` installs `.github/workflows/specguard-readiness-gate.yml` by default. Use `specguard init <feature> --no-actions` to opt out, or `specguard actions install-readiness-gate` to install the workflow later.

Repositories that want merge-time enforcement should add `SpecGuard Readiness Gate` to branch protection or ruleset required status checks.

`SpecGuard PR Review` is separate from the readiness gate. It is a post-implementation advisory review that checks whether code appears aligned with the approved spec package.

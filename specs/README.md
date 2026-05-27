# Spec Packages

This directory is the default root for SpecGuard feature packages.

Create one directory per feature:

```text
specs/<feature-name>/
|-- discovery.md
|-- spec.md
|-- plan.md
|-- tasks.md
|-- constitution.md
`-- checklists/
    `-- spec-readiness.md
```

Run SpecGuard against a feature package:

```bash
specguard run specs/<feature-name>
```

Nested module packages such as `services/api/specs/<feature-name>/` remain supported. Keep this root `specs/` entry point for repositories that use the default package location.

# Contributing to SpecGuard

SpecGuard contributions must preserve the core workflow:

```text
Discovery -> Spec Refinement -> Technical Design -> SpecGuard Review -> Test -> Contract -> Implementation Outputs
```

## Required Workflow

All contributions must include:

- A written discovery artifact
- A reviewed and strengthened spec
- A written technical design
- A SpecGuard Review result
- Tests or test scenarios
- Contracts when the feature exposes an API

## PR Rules

- No discovery -> reject
- No spec -> reject
- No technical design -> reject
- No test -> reject
- Failed validation -> reject

## Repository Language

All public repository-facing content must be written in English, including:

- Issues
- Pull request titles and descriptions
- Commit messages
- Release notes
- Labels and milestones
- GitHub Discussions and review comments

## Branch Strategy

```text
main
`-- develop
    |-- feature/*
    `-- fix/*
```

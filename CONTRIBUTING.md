# Contributing to SpecGuard

SpecGuard contributions must preserve the core workflow:

```text
Discovery -> Spec Refinement -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs
```

## Required Workflow

All contributions must include:

- A written discovery artifact
- A reviewed and strengthened spec
- A written technical design
- A Grill Me result
- Tests or test scenarios
- Contracts when the feature exposes an API

## PR Rules

- No discovery -> reject
- No spec -> reject
- No technical design -> reject
- No test -> reject
- Failed validation -> reject

## Branch Strategy

```text
main
`-- develop
    |-- feature/*
    `-- fix/*
```

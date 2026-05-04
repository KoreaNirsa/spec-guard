# Contributing to SpecGuard

SpecGuard contributions must preserve the core workflow:

```text
Discovery -> Spec -> Technical Design -> Grill -> Test -> Contract -> Implementation Outputs
```

## Required Workflow

All contributions must include:

- A written discovery artifact
- A written spec
- A written technical design
- A Grill Me result
- Tests or test scenarios

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

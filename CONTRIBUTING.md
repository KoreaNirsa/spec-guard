# Contributing to SpecGuard

SpecGuard contributions must preserve the core workflow:

```text
Spec -> Design -> Grill -> Test -> Code
```

## Required Workflow

All contributions must include:

- A written spec
- A written design
- A Grill Me result
- Tests or test scenarios

## PR Rules

- No spec -> reject
- No design -> reject
- No test -> reject
- Failed validation -> reject

## Branch Strategy

```text
main
└── develop
    ├── feature/*
    └── fix/*
```

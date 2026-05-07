# Verification Contract: Team Invite

status: accepted
command: run the backend and frontend test suites generated for the implementation stack

## Required Evidence

- Backend API tests cover create, duplicate pending, revoke, accept, token replay, wrong workspace, email mismatch, idempotency, email timeout, and concurrent acceptance.
- Contract tests verify `contracts/openapi.yaml` response schemas and stable error codes.
- Audit tests verify correlation id and audit event creation for successful and rejected write paths.
- Frontend tests cover admin invite creation, delivery failure display, sign-in redirect, successful acceptance, and rejected token states.

## Acceptance Rule

SpecGuard may hand off this sample after the spec package is READY because the implementation agent must preserve or replace this contract with executable tests for the selected stack.

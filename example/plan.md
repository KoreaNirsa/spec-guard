# Implementation Plan: Team Invite

## Objective

- Deliverable: Workspace admins can invite a teammate by email, and invited users can accept into the correct workspace after authentication.
- Success outcome: Membership is created only after authorization, token, workspace, invited-email ownership, idempotency, and duplicate checks pass.
- Implementation may start only after SpecGuard Review reports implementation-ready status.

## Scope

- In scope: Invite creation, duplicate pending invite handling, idempotency, token acceptance, invite revocation, audit events, stable error responses, and one email delivery attempt.
- Out of scope: Bulk invites, SCIM provisioning, billing seat enforcement, custom email templates, automatic email retry queues, and OAuth provider implementation.
- Non-negotiable constraints: No membership is created from an invalid, expired, revoked, reused, wrong-workspace, unauthenticated, or email-mismatched token.

## Technical Context

- Data and entities: Workspace, admin user, invited user, invitee email, invite token id, invite token hash, invite status, membership, idempotency record, audit event.
- Dependencies: User directory, workspace membership store, email provider, token signing service, clock source, audit log, idempotency store.
- Required downstream artifacts: `technical-design.md`, `tests/`, `contracts/`, and `implementation-output.md`.

## Technology Stack

- Frontend: React 19 with TypeScript and Vite for the admin invite form, invite acceptance screen, sign-in redirect state, and status feedback.
- Frontend routing: React Router handles invite links using a URL fragment token, immediately removes the fragment from the visible URL, carries only a random pending-invite nonce through sign-in redirects, and submits the token to `POST /invites/accept` in the request body so servers never receive the token in URL path, query, or redirect parameters.
- Frontend testing: Vitest and React Testing Library for form validation, success states, rejected token states, email mismatch states, and duplicate-submit handling.
- Backend: Java 21 with Spring Boot 3.x.
- API layer: Spring Web MVC REST controllers with request validation through Jakarta Bean Validation.
- Security: Spring Security for authenticated admin checks, workspace role enforcement, invited-email matching, and correlation-id propagation.
- Persistence: PostgreSQL 16 with Spring Data JPA and Flyway migrations.
- Token handling: HMAC-SHA256 signed invite tokens with explicit `schema_version`, issued-at, expires-at, token id, invite id, workspace id, and invitee email claims.
- Email integration: Spring service adapter around the email provider with a 3-second timeout and no automatic retry in v1.
- Audit logging: Durable audit-event table written by the Spring application service for successful and rejected write paths.
- Backend testing: JUnit 5, Spring Boot Test, MockMvc, and Testcontainers PostgreSQL for API, authorization, persistence, token, idempotency, concurrency, and audit scenarios.
- Contract format: OpenAPI 3.1 for invite creation, revocation, and acceptance endpoints.

## Quality Gates

- Discovery and spec validation pass.
- Technical design is already authored for the example and must be regenerated only after meaningful spec changes.
- SpecGuard Review readiness is implementation-ready before tests, contracts, and implementation output are trusted.
- Verification evidence exists through `tests/verification-contract.md`.
- Coding agents consume only the approved implementation package.

## Risk Controls

- Token replay is blocked by accepted, revoked, expired, token-id hash, and row-level transition checks.
- Storage writes occur only after authentication, authorization, token envelope validation, invited-email ownership validation, and duplicate membership checks.
- A database uniqueness rule prevents multiple active pending invites for the same workspace and normalized email.
- A transaction or compare-and-set update serializes concurrent acceptance so exactly one membership can be created.
- Email delivery failure does not roll back the invite record in v1; it sets `delivery_status=failed`.
- Audit events include actor id when authenticated, workspace id when known, invite id when known, outcome, error code when rejected, and correlation id.

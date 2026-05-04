# Implementation Plan: Team Invite

## Objective

- Deliverable: Workspace admins can invite a teammate by email, and invited users can accept into the correct workspace.
- Success outcome: Membership is created only after authorization, token, workspace, and duplicate checks pass.
- Implementation may start only after SpecGuard Review reports implementation-ready status.

## Scope

- In scope: Invite creation, duplicate pending invite handling, token acceptance, invite revocation, audit events, stable error responses.
- Out of scope: Bulk invites, SCIM provisioning, billing seat enforcement, custom email templates, automatic email retry queues.
- Non-negotiable constraints: No membership is created from an invalid, expired, revoked, reused, or wrong-workspace token.

## Technical Context

- Data and entities: Workspace, admin user, invitee email, invite token, invite status, membership, audit event.
- Dependencies: User directory, workspace membership store, email provider, token signing service, audit log.
- Required downstream artifacts: `technical-design.md`, `tests/`, `contracts/`, and `implementation-output.md`.

## Technology Stack

- Frontend: React 19 with TypeScript and Vite for the admin invite form, invite acceptance screen, and status feedback.
- Frontend routing: React Router with route-level handling for invite token acceptance links.
- Frontend testing: Vitest and React Testing Library for form validation, success states, rejected token states, and duplicate-submit handling.
- Backend: Java 21 with Spring Boot 3.x.
- API layer: Spring Web MVC REST controllers with request validation through Jakarta Bean Validation.
- Security: Spring Security for authenticated admin checks, workspace role enforcement, and correlation-id propagation.
- Persistence: PostgreSQL 16 with Spring Data JPA and Flyway migrations.
- Token handling: HMAC-SHA256 signed invite tokens with explicit `schema_version`, issued-at, expires-at, invite id, workspace id, and invitee email claims.
- Email integration: Spring service adapter around the email provider with configured timeout handling and no automatic retry in v1.
- Audit logging: Durable audit-event table written by the Spring application service for successful and rejected write paths.
- Backend testing: JUnit 5, Spring Boot Test, MockMvc, and Testcontainers PostgreSQL for API, authorization, persistence, token, and audit scenarios.
- Contract format: OpenAPI 3.1 for invite creation, revocation, and acceptance endpoints.

## Quality Gates

- Discovery and spec validation pass.
- Technical design is regenerated after meaningful spec changes.
- SpecGuard Review readiness is implementation-ready before tests, contracts, and implementation output are trusted.
- Coding agents consume only the approved implementation package.

## Risk Controls

- Token replay is blocked by accepted/revoked/expired state checks.
- Storage writes occur only after authentication, authorization, and envelope validation.
- Email delivery failure does not roll back the invite record in v1; it sets `delivery_status=failed`.
- Audit events include actor id, workspace id, invite id when available, outcome, error code when rejected, and correlation id.

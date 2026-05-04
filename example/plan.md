# Implementation Plan: Team Invite

## Objective

- Deliverable: Workspace admins can invite a teammate by email, and invited users can accept into the correct workspace.
- Success outcome: Membership is created only after authorization, token, workspace, and duplicate checks pass.
- Implementation may start only after Grill Review reports implementation-ready status.

## Scope

- In scope: Invite creation, duplicate pending invite handling, token acceptance, invite revocation, audit events, stable error responses.
- Out of scope: Bulk invites, SCIM provisioning, billing seat enforcement, custom email templates, automatic email retry queues.
- Non-negotiable constraints: No membership is created from an invalid, expired, revoked, reused, or wrong-workspace token.

## Technical Context

- Data and entities: Workspace, admin user, invitee email, invite token, invite status, membership, audit event.
- Dependencies: User directory, workspace membership store, email provider, token signing service, audit log.
- Required downstream artifacts: `technical-design.md`, `tests/`, `contracts/`, and `implementation-output.md`.

## Quality Gates

- Discovery and spec validation pass.
- Technical design is regenerated after meaningful spec changes.
- Grill Review readiness is implementation-ready before tests, contracts, and implementation output are trusted.
- Coding agents consume only the approved implementation package.

## Risk Controls

- Token replay is blocked by accepted/revoked/expired state checks.
- Storage writes occur only after authentication, authorization, and envelope validation.
- Email delivery failure does not roll back the invite record in v1; it sets `delivery_status=failed`.
- Audit events include actor id, workspace id, invite id when available, outcome, error code when rejected, and correlation id.


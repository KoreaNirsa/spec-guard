# Technical Design: Team Invite

## Architecture

- Feature boundary: Team invite APIs create, revoke, and accept workspace-scoped email invites.
- Frontend boundary: React screens collect invite email, display delivery status, route invite links, and redirect unauthenticated invitees to sign in or sign up before API acceptance.
- Backend boundary: Spring Boot controllers validate requests, delegate invite lifecycle decisions to an application service, and return OpenAPI-compatible responses.
- Security boundary: Spring Security authenticates actors, verifies workspace admin permission for create/revoke, and verifies invited-email ownership for acceptance.
- Persistence boundary: PostgreSQL stores invites, token id hashes, memberships, idempotency records, and audit events.
- Contract boundary: `contracts/openapi.yaml` is the API contract for create, revoke, accept, success responses, and error responses.

## Data Flow

1. Admin sends `POST /workspaces/{workspaceId}/invites` with an email and optional `Idempotency-Key`.
2. API validates authentication, admin permission, workspace active state, email shape, normalized email, duplicate membership, duplicate pending invite, and idempotency record.
3. Application service creates or returns the pending invite, signs a token containing `schema_version=team_invite.v1`, invite id, token id, workspace id, email, issued-at, and expires-at.
4. Email adapter attempts one send with a 3-second timeout and records `delivery_status=sent` or `delivery_status=failed`.
5. System writes an audit event and returns `InviteResponse` with `schema_version=team_invite.response.v1` and `correlation_id`.
6. Invited user follows the browser link; the UI redirects unauthenticated users to sign in or sign up.
7. Authenticated user sends `POST /invites/{token}/accept`.
8. API validates token signature, schema version, token id hash, expiration, invite status, workspace state, existing membership, and verified email match.
9. Acceptance transaction serializes the invite row, creates exactly one membership, marks the invite accepted, writes an audit event, and returns `InviteAcceptResponse`.

## State

- Invite states: `pending`, `accepted`, `revoked`, `expired`.
- Delivery states: `sent`, `failed`.
- Valid transitions:
  - none -> `pending` during create.
  - `pending` -> `accepted` during successful acceptance.
  - `pending` -> `revoked` during admin revocation.
  - `pending` -> `expired` when server clock passes `expires_at`.
- Invalid transitions:
  - `accepted`, `revoked`, or `expired` cannot return to `pending`.
  - `accepted`, `revoked`, or `expired` cannot create membership.
  - A token for one workspace cannot create membership in another workspace.
- Concurrency rule: acceptance uses row locking or compare-and-set on `pending` so exactly one concurrent request can transition to `accepted`.

## Dependencies

- User directory: supplies authenticated user id and verified email.
- Workspace membership store: verifies admin permission, existing membership, and creates membership.
- Email provider: sends invite email once with a 3-second timeout; failure sets `delivery_status=failed`.
- Token signing service: signs and verifies HMAC-SHA256 invite tokens.
- Clock source: calculates `issued_at`, `expires_at`, and expiration using UTC.
- Audit log: records every successful and rejected write path with actor id when authenticated, workspace id when known, invite id when known, outcome, error code when rejected, and correlation id.
- Idempotency store: keeps 24-hour response records keyed by workspace, requester, endpoint, and `Idempotency-Key`.

## Failure Handling

- Invalid email returns `400 INVALID_EMAIL` before invite persistence.
- Missing authentication returns `401 UNAUTHENTICATED` before state changes.
- Non-admin create or revoke returns `403 FORBIDDEN`.
- Archived or deleted workspace returns `409 WORKSPACE_NOT_ACTIVE`.
- Existing membership returns `409 ALREADY_MEMBER`.
- Duplicate pending invite returns `200 OK` with the existing invite and writes a duplicate-returned audit event.
- Reused idempotency key with a different request body returns `409 IDEMPOTENCY_KEY_REUSED`.
- Email provider timeout returns `201 Created` with `delivery_status=failed`; no automatic retry occurs in v1.
- Invalid token envelope, signature, token id, or schema version returns `400 INVALID_INVITE_TOKEN`.
- Expired, revoked, or accepted tokens return the matching stable error code and create no membership.
- Authenticated email mismatch returns `403 INVITEE_EMAIL_MISMATCH`.
- Concurrent acceptance losers return `409 INVITE_ALREADY_ACCEPTED`.

## Implementation Blockers

- None for the sample package. If implementation changes token shape, idempotency, email timeout, ownership checks, or concurrency behavior, update `spec.md`, `contracts/openapi.yaml`, and verification artifacts before coding.

# Feature Specification: Team Invite

**Status**: Example spec package seed
**Source**: `discovery.md`

## User Scenarios & Testing

### Primary User Story

As a workspace admin, I want to invite a teammate by email so that the teammate can join the correct workspace without manual account setup.

### Acceptance Scenarios

1. Given an active workspace admin and a valid non-member email, when the admin creates an invite, then the system creates one pending invite, sends or records one email delivery attempt, writes an audit event, and returns the invite id, status, expiration, delivery status, and correlation id.
2. Given a duplicate invite request for the same workspace and normalized email while a pending invite exists, when the admin creates another invite, then the system returns the existing pending invite with `200 OK`, does not issue a second active token, and writes a duplicate-returned audit event.
3. Given an authenticated invited user whose verified email matches the invitee email and a valid unexpired token, when they accept the invite, then the system creates exactly one workspace membership, marks the invite as accepted, invalidates further token use, and returns the membership id.
4. Given an expired, revoked, accepted, malformed, wrong-workspace, or email-mismatched token, when acceptance is attempted, then the system rejects the request, creates no membership, and writes an audit event with the stable error code.

### Edge Cases

- Invitee email differs only by case or surrounding whitespace.
- Invitee is already a workspace member.
- Workspace is archived or deleted after invite creation.
- Email delivery provider times out after the invite record is created.
- Acceptance is submitted twice with the same token or concurrently from two requests.
- Non-admin attempts to create or revoke an invite.
- Authenticated user attempts to accept a token for a different verified email.

## Requirements

### Functional Requirements

- The system must require an authenticated workspace admin with `workspace.invites.manage` permission to create or revoke an invite.
- The system must require an authenticated user with a verified email matching the normalized invitee email to accept an invite.
- The browser acceptance flow may redirect unauthenticated users to sign in or sign up, but the acceptance API must return `401 UNAUTHENTICATED` until authentication is complete.
- The system must normalize invitee email by trimming whitespace and lowercasing the full address before duplicate checks, token claims, and email-match checks.
- The system must create invites with status `pending`, `accepted`, `revoked`, or `expired`.
- The system must issue a signed invite token with `schema_version=team_invite.v1`, invite id, token id, workspace id, normalized invitee email, issued-at timestamp, and expires-at timestamp.
- The system must store only a hash of the token id for replay detection and must never store the full token after returning or sending it.
- Invite email links must carry the signed invite token only in the URL fragment, for example `/invites/accept#invite_token=...`, so servers, CDNs, access logs, and referrer headers do not receive the token.
- The browser acceptance route must read the fragment, immediately remove it with `history.replaceState`, keep the token out of all path, query, and auth redirect parameters, and submit it to the HTTPS acceptance API request body only after authentication.
- If sign-in or sign-up is required, the redirect state may contain only a random pending-invite nonce; the token itself must remain in client-side ephemeral invite state with a 10-minute TTL and must be cleared after acceptance or rejection.
- The acceptance API must not carry the full invite token in a URL path or query string; clients submit it in the HTTPS request body and server logs/traces must redact fields named `token`.
- The system must expire invite tokens exactly 7 days after creation using the server clock in UTC.
- The system must treat invites with `expires_at <= now` as expired before duplicate pending invite checks and must enforce one active pending invite per workspace and normalized email with a durable uniqueness rule.
- The system must make invite creation idempotent for the same workspace, normalized email, requester, and optional `Idempotency-Key` within a 24-hour window.
- The system must reject reused idempotency keys with a different request body using `IDEMPOTENCY_KEY_REUSED`.
- The system must call the email provider at most once in v1 with a 3-second timeout.
- The system must keep the invite pending and set `delivery_status=failed` when the email provider times out or returns an error; no automatic retry occurs in v1.
- The system must create an audit event for invite created, invite delivery failed, invite accepted, invite revoked, duplicate invite returned, idempotency replay, and invalid acceptance attempt.
- The system must reject invite acceptance if the workspace is archived, deleted, or does not match the token workspace id.
- The system must never create membership before token validation, workspace validation, invited-email ownership validation, and duplicate membership checks complete.
- The system must serialize concurrent acceptance attempts so exactly one request can transition a pending invite to accepted.
- The system must return stable machine-readable error codes and a correlation id for every documented error response.

### API Requirements

- `POST /workspaces/{workspaceId}/invites` creates or returns a pending invite.
- `DELETE /workspaces/{workspaceId}/invites/{inviteId}` revokes a pending invite.
- `POST /invites/accept` accepts an invite for the authenticated invited user using a JSON body with `token`.
- All write responses must include `schema_version=team_invite.response.v1` and `correlation_id`.
- Error responses must use the shared `ErrorResponse` schema in `contracts/openapi.yaml`.

## Acceptance Criteria

- [ ] Admin invite creation with a valid email returns `201 Created` with `status=pending`, `schema_version=team_invite.response.v1`, `expires_at`, `delivery_status`, and an invite id.
- [ ] Duplicate pending invite creation returns `200 OK` with the existing invite id, does not issue a second active token, and writes `DUPLICATE_PENDING_INVITE` to the audit log.
- [ ] Non-admin invite creation returns `403 FORBIDDEN` and does not persist an invite.
- [ ] Reused idempotency key with the same request body returns the original response; reused idempotency key with a different body returns `409 IDEMPOTENCY_KEY_REUSED`.
- [ ] Email provider timeout returns `201 Created` with `delivery_status=failed`, leaves the invite pending, writes an audit event, and performs no automatic retry in v1.
- [ ] Valid invite acceptance by an authenticated user with a matching verified email returns `201 Created`, creates exactly one membership, marks the invite accepted, and rejects subsequent token reuse.
- [ ] Unauthenticated acceptance returns `401 UNAUTHENTICATED`; authenticated email mismatch returns `403 INVITEE_EMAIL_MISMATCH`; both create no membership.
- [ ] Expired, revoked, accepted, malformed, or wrong-workspace tokens return stable error codes and create no membership.
- [ ] Concurrent acceptance attempts for the same pending token result in one `201 Created` response and all other attempts returning `409 INVITE_ALREADY_ACCEPTED`.
- [ ] Invite revocation by an admin returns `200 OK`, changes only pending invites to revoked, invalidates the token, and writes an audit event; missing, wrong-workspace, accepted, revoked, or expired invites return stable error codes and do not change membership.
- [ ] Every successful and rejected write path emits a correlation id and audit event containing actor id when authenticated, workspace id when known, invite id when known, outcome, and error code when rejected.

## Error Cases

- Missing or invalid email returns `INVALID_EMAIL`.
- Missing authentication returns `UNAUTHENTICATED`.
- Authenticated user without workspace admin role returns `FORBIDDEN`.
- Workspace is archived or deleted returns `WORKSPACE_NOT_ACTIVE`.
- Duplicate pending invite returns existing invite with `DUPLICATE_PENDING_INVITE` in the audit event.
- Reused idempotency key with a different request body returns `IDEMPOTENCY_KEY_REUSED`.
- Invitee is already a member returns `ALREADY_MEMBER`.
- Expired token returns `INVITE_EXPIRED`.
- Revoked token returns `INVITE_REVOKED`.
- Accepted token reuse returns `INVITE_ALREADY_ACCEPTED`.
- Token signature, token id, or schema version mismatch returns `INVALID_INVITE_TOKEN`.
- Authenticated user email mismatch returns `INVITEE_EMAIL_MISMATCH`.
- Workspace id in token does not match the persisted invite workspace id returns `WRONG_WORKSPACE`.
- Revoking an unknown invite id or an invite outside the path workspace returns `INVITE_NOT_FOUND`.
- Revoking an accepted, revoked, or expired invite returns `INVITE_NOT_PENDING`.
- Email provider timeout returns success for invite creation with `delivery_status=failed`; no automatic retry occurs in v1.

## Key Entities

- Workspace: tenant boundary for invite and membership.
- Admin user: authenticated actor with permission to create and revoke teammate invites.
- Invited user: authenticated actor whose verified email must match the invitee email before acceptance.
- Invite: pending access grant for one workspace and normalized email.
- Invite token: signed acceptance credential scoped to one invite, token id, email, and workspace.
- Membership: durable relationship between user and workspace.
- Idempotency record: 24-hour record keyed by workspace, requester, endpoint, and idempotency key.
- Audit event: immutable record of invite lifecycle and rejected write attempts.

## Out of Scope

- Bulk invite import.
- SCIM or directory sync.
- Billing seat purchase or payment enforcement.
- Custom email template editing.
- Automatic retry queues for failed email delivery.
- Cross-workspace invites from one token.
- OAuth provider implementation beyond using the existing authenticated user identity.

## Review & Acceptance Checklist

- [ ] Requirements are observable and testable.
- [ ] Authorization, ownership, and workspace boundaries are explicit.
- [ ] Invite token lifecycle is deterministic.
- [ ] Duplicate, concurrent, expired, revoked, and replay cases are covered.
- [ ] Email delivery failure is explicit and does not decide membership state.
- [ ] Contract and verification artifacts are ready before implementation handoff.

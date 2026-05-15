# Discovery: Team Invite

## Foundation

- Goal: Let workspace admins invite a new teammate by email and let the invited person accept into the correct workspace.
- Users: Workspace admins, invited teammates, and support engineers who audit invite issues.
- Constraints: The first release supports email-only invites, one workspace per invite, browser-based acceptance, and no automatic email retry queue.
- Desired outcomes: Admins can invite teammates safely, invited users can join only the intended workspace, and expired, revoked, reused, or mismatched invites cannot grant access.

## Mechanisms

- Feature focus: Team invite creation, delivery, revocation, acceptance, expiration, duplicate handling, and auditability.
- Main flows: Admin creates invite, system validates workspace permission, invite token is issued, email is sent or marked failed, invited user signs in with the invited email, token is accepted, membership is created.
- Data and entities: Workspace, admin user, invited user, invitee email, invite id, invite token id, invite token hash, invite status, membership, idempotency key, audit event, correlation id.
- Dependencies: User directory, workspace membership store, email provider, token signing service, clock source, audit log, idempotency store.

## Stress Test

- Failure and abuse risks: Invite token replay, invite sent by non-admin, email provider timeout, expired invite acceptance, revoked invite acceptance, invite for an already-member email, authenticated user accepting an invite for a different email.
- Boundary conditions: Missing email, invalid email, duplicate pending invite, reused idempotency key with a different body, workspace archived or deleted before acceptance, simultaneous accept requests for the same token.
- Recovery expectation: Unsafe or ambiguous invite state blocks membership creation and returns a stable machine-readable error code. Email delivery failure never creates membership and does not erase the pending invite.

## Differentiation

- Existing option: Manually create users or share a generic signup link.
- Difference: SpecGuard validates an explicit invite lifecycle before implementation, including authorization, token state, duplicate behavior, API contract, and acceptance evidence.
- Non-goals: Bulk invite import, SCIM provisioning, identity-provider setup, billing seat purchase, automatic retry queues, and custom email templates.

## Feasibility

- Initial scope: API-level invite creation, revocation, and acceptance with audit events and contract-ready responses.
- Blocker: Missing token expiration, missing admin authorization, missing duplicate invite policy, missing invited-email ownership check, or missing concurrency behavior.
- Validation: Acceptance criteria, error cases, idempotency, token lifecycle, ownership checks, API contract, and audit behavior are explicit.

## Improvement

- Simplify: Use a single invite token version, one email delivery attempt in v1, and a fixed 7-day expiration.
- Automate later: Add bulk invites, retry queues, admin notification dashboards, and provider-specific email templates after the lifecycle is stable.
- Accepted decision: Production email template id is configured outside this feature. The API records only `delivery_status` and the provider message id when available.

## Synthesis

- Decision: Build only after invite lifecycle, ownership, authorization, contract, verification, and error semantics pass SpecGuard Review.
- Required artifacts: spec.md, plan.md, tasks.md, constitution.md, checklists/spec-readiness.md, technical-design.md, tests, contracts, and implementation-output.md.
- Stop condition: Do not start code implementation while SpecGuard reports NOT_READY.

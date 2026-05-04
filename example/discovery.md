# Discovery: Team Invite

## Foundation

- Goal: Let workspace admins invite a new teammate by email and let the invited person accept into the correct workspace.
- Users: Workspace admins, invited teammates, and support engineers who audit invite issues.
- Constraints: The first release supports email-only invites, one workspace per invite, and browser-based acceptance.
- Desired outcomes: Admins can invite teammates safely, invited users can join the intended workspace, and expired or reused invites cannot grant access.

## Mechanisms

- Feature focus: Team invite creation, delivery, acceptance, expiration, and auditability.
- Main flows: Admin creates invite, system validates workspace permission, invite token is issued, email is sent, invited user accepts, membership is created.
- Data and entities: Workspace, admin user, invitee email, invite token, invite status, membership, audit event.
- Dependencies: User directory, workspace membership store, email provider, token signing service, audit log.

## Stress Test

- Failure and abuse risks: Invite token replay, invite sent by non-admin, email provider timeout, expired invite acceptance, invite for an already-member email.
- Boundary conditions: Missing email, invalid email, duplicate pending invite, revoked invite, expired token, workspace deleted before acceptance.
- Recovery expectation: Unsafe or ambiguous invite state blocks membership creation and returns a stable error.

## Differentiation

- Existing option: Manually create users or share a generic signup link.
- Difference: SpecGuard validates an explicit invite lifecycle before implementation.
- Non-goals: Bulk invite import, SCIM provisioning, identity-provider setup, billing seat purchase, and custom email templates.

## Feasibility

- Initial scope: API-level invite creation and acceptance with audit events and contract-ready responses.
- Blocker: Missing token expiration, missing admin authorization, or missing duplicate invite policy.
- Validation: Acceptance criteria, error cases, idempotency, token lifecycle, and audit behavior are explicit.

## Improvement

- Simplify: Use a single invite token version and one email delivery attempt in v1.
- Automate later: Add bulk invites, retry queues, and admin notification dashboards after the lifecycle is stable.
- Open question: Which email provider template id will production use?

## Synthesis

- Decision: Build only after invite lifecycle, ownership, authorization, and error semantics pass Grill Review.
- Required artifacts: spec.md, plan.md, tasks.md, constitution.md, checklists/spec-readiness.md, technical-design.md, tests, contracts, and implementation-output.md.
- Stop condition: Do not start code implementation while Critical or Major Grill Review findings remain.

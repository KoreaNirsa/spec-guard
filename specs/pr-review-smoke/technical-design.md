# Technical Design: PR Review Smoke

## Architecture

- API layer receives the authenticated owner id.
- Notes service owns all filtering and must pass the owner id into repository queries.
- Repository access must be owner-scoped before results leave the service boundary.

## Data Flow

1. Caller sends a list-notes request with an authenticated owner id.
2. API layer rejects missing owner id with `401 Unauthorized`.
3. Notes service queries notes by `owner_id`.
4. Response serializes only notes matching the authenticated owner.

## State

- Initial state: request received.
- Valid state: owner id present and repository query is owner-scoped.
- Invalid state: missing owner id or cross-owner note included in response.
- Terminal state: owned notes returned or documented error returned.

## Dependencies

- In-memory notes repository for smoke testing.
- API contract in `contracts/openapi.yaml`.

## Failure Handling

- Missing owner id returns `401 Unauthorized`.
- Cross-owner exposure is a blocker and must not be accepted.

## Implementation Blockers

- None.

# Spec: PR Review Smoke

## Problem

SpecGuard PR Reviewer should identify when implementation evidence contradicts approved ownership requirements.

## Requirements

- The system must list private notes for the authenticated owner only.
- The system must reject requests without an authenticated owner id.
- The system must never return notes owned by a different user.

## Acceptance Criteria

- [ ] Given owner `alice`, the list operation returns only notes with `owner_id=alice`.
- [ ] Given owner `bob`, the list operation returns only notes with `owner_id=bob`.
- [ ] Missing owner id returns `401 Unauthorized`.

## Error Cases

- Missing owner id returns `401 Unauthorized`.
- Cross-owner note exposure is forbidden.

## Key Entities

- Note: private text record with `id`, `owner_id`, and `body`.
- Authenticated owner: identity boundary used to filter notes.

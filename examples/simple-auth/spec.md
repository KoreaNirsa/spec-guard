# Spec: simple-auth

## Problem

Users need to authenticate with an email and password before accessing protected resources.

## Requirements

- The system must authenticate users with valid credentials.
- The system must reject invalid credentials.
- The system must prevent access to protected resources without authentication.

## Acceptance Criteria

- [ ] Valid credentials return an access token.
- [ ] Invalid credentials return an authentication error.
- [ ] Missing credentials return a validation error.

## Error Cases

- Missing email
- Missing password
- Invalid password
- Unknown user

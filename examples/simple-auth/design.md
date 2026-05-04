# Design: simple-auth

## Architecture

The API receives login requests, validates credentials through an auth service, and returns an access token.

## Data Flow

1. Client submits email and password.
2. API validates request shape.
3. Auth service verifies credentials.
4. Token service issues an access token.
5. API returns token or error response.

## State

- Initial state: unauthenticated
- Valid states: unauthenticated, authenticated
- Invalid states: authenticated without issued token
- Terminal state: authenticated or rejected

## Dependencies

- User store
- Token signer

## Failure Handling

- Invalid credentials return a generic authentication error.
- Token signing failures return a server error and do not authenticate the user.

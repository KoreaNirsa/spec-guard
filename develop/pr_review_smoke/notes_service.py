NOTES = [
    {"id": "n1", "owner_id": "alice", "body": "Alice private note"},
    {"id": "n2", "owner_id": "bob", "body": "Bob private note"},
]


def list_notes(owner_id: str) -> list[dict[str, str]]:
    if not owner_id:
        raise PermissionError("missing owner id")

    # Deliberately flawed smoke implementation: the approved spec requires owner filtering.
    return NOTES

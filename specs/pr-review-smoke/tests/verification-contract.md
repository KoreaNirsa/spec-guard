# Verification Contract

Status: accepted
Command: python -m pytest tests/test_notes_contract.py
Artifact: Owner-scoped note list tests must assert that every returned note has the authenticated `owner_id`.

The smoke implementation intentionally violates this contract so SpecGuard PR Reviewer has a clear spec-to-code mismatch to report.

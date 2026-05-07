from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Iterator


_LOCK = threading.Lock()
_ACTIVITY: str | None = None


def current_progress_activity() -> str | None:
    with _LOCK:
        return _ACTIVITY


@contextmanager
def progress_activity(activity: str | None) -> Iterator[None]:
    global _ACTIVITY
    if not activity:
        yield
        return

    with _LOCK:
        previous = _ACTIVITY
        _ACTIVITY = activity
    try:
        yield
    finally:
        with _LOCK:
            _ACTIVITY = previous

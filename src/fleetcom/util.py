"""Small shared helpers: ids, timestamps, and capped list fetches."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

DEFAULT_LIMIT = 50
MAX_LIMIT = 1_000_000


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def capped(
    fetch: Callable[[int], list[dict]], limit: int = DEFAULT_LIMIT
) -> tuple[list[dict], bool]:
    """Fetch one row past `limit`, so a cut list can say it was cut."""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    rows = fetch(limit + 1)
    return rows[:limit], len(rows) > limit

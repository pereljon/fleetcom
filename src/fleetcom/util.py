"""Small shared helpers: ids, timestamps, and capped list fetches."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

DEFAULT_LIMIT = 50
MAX_LIMIT = 1_000_000
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).strftime(_UTC_FORMAT)


def to_utc(value: str | None) -> str | None:
    """Rewrite an ISO-8601 time in now_iso()'s UTC format, so string order is time order.

    A time without an offset is read as UTC. An empty string clears the field.
    """
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).strftime(_UTC_FORMAT)
    except (ValueError, OverflowError):
        raise ValueError(f"not an ISO-8601 time: {value!r}") from None


def normalize_times(fields: dict, names: tuple[str, ...]) -> dict:
    result = dict(fields)
    for name in names:
        if name in result:
            try:
                result[name] = to_utc(result[name])
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from None
    return result


def capped(
    fetch: Callable[[int], list[dict]], limit: int = DEFAULT_LIMIT
) -> tuple[list[dict], bool]:
    """Fetch one row past `limit`, so a cut list can say it was cut."""
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    rows = fetch(limit + 1)
    return rows[:limit], len(rows) > limit

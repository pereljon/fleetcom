"""Small shared helpers: ids and timestamps."""

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

# Status Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the eight prioritized items from the 2026-11-14 status review, then ship them in one promote with live checks on every client.

**Architecture:** Four sequential branches, each merged to `main` before the next starts: unknown-id errors (A), database open safety (B), UTC timestamps (C), and promote hardening with `--version` (D). One promote follows, then a restart of every client and the live checks. Every change stays inside the existing modules; no new module is added.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, `mcp>=2.2,<2.3` (`MCPServer`), pytest with pytest-asyncio, ruff, uv 0.13.6, bash.

Investigated against `main` at `61777b0`, uv 0.13.6, and SQLite 3.53.1.

## Global Constraints

- Run tests with `uv run pytest -q`. Run lint with `uv run ruff check` and `uv run ruff format --check`.
- Run the tests and linters before each branch starts, so failures that already exist are not attributed to the branch. The baseline on 2026-11-14 was 99 passed and both linters clean.
- Give every test a timeout path; use no sleeps. Use `asyncio.wait_for` or a bounded `busy_timeout` where a call could block.
- Keep the tool count at 15. Keep every update and delete response shaped `{"ok": bool}`.
- Never interpolate a caller-supplied name into SQL. Table and column names in SQL text come from module literals only (`dev/SKELETON.md`, Key Invariants).
- Run every write inside `with conn:`.
- Never read, copy, or change the live database (`~/.fleetcom/fleetcom.db`) without the user's go-ahead for that step.
- Never edit files outside this repo. Hermes configs, `~/.claude.json`, and `~/.codex/config.toml` belong to the user or hermes-manager.
- Write a design doc and test plan (`dev/features/<name>.md`, `<name>-tests.md`) at the start of each branch, from that branch's section below. Review the test plan with the user before writing code (`development/AGENTS.md`, Testing).
- Commit on the branch without approval and report the hash. Merging to `main` needs the user's approval and a reviewer subagent ("Code review before a merge").

## Ordering and dependencies

| Order | Branch | Status review item | Size | Depends on |
|---|---|---|---|---|
| 1 | `unknown-id-errors` (A) | 1 | small | none |
| 2 | `db-open-safety` (B) | 3, 7, part of 8 (file modes) | small to medium | none |
| 3 | `utc-timestamps` (C) | 2, part of 8 (`due=""`) | medium | B (`db.migrate` and `server.main` change in B first) |
| 4 | `promote-hardening` (D) | 6, part of 8 (deploy docs) | small to medium | B (`_parse_args` exists) |
| 5 | promote and live checks (E) | 5, part of 8 (Codex checks, Hermes follow-ups) | small | A to D merged; user authorizes |

Item 4 of the review (delete the Hermes handoff files) was done on 2026-11-14 in `61777b0`.

The order differs from the review's priority in one place: B runs before C. C adds a startup repair step to `server.main`, and B rewrites `server.main` and `db.migrate`. Doing B first means C edits the final shape once. A and B touch `server.py` in different functions, so their order does not matter.

Batching one promote at the end means one client restart instead of four. The list-truncation live checks (item 5) wait until then. See Question Q6 for the alternative.

## Keep-out list

Do not edit these files in any task:

- `deploy/` (written only by `scripts/promote.sh`).
- `uv.lock`, except regenerating it with `uv lock` after the version bump in Task E1. The lock pins the project's own version, so a bump without it leaves the lock stale.
- `dev/features/db-move.md`, `db-move-tests.md`, `list-truncation.md` (shipped designs). Append to `list-truncation-tests.md` only under `## Results`.
- Past entries under `## Decisions` in `docs/ISSUES.md`. Add new dated entries instead.
- `LICENSE`, `.python-version`, `pyproject.toml` (except the version bump in Task E1).

## How to continue if interrupted

1. Run `git branch --show-current` and `git log --oneline -10` to find the branch and the last commit.
2. Find the first unchecked step in this file for that branch.
3. Read `docs/ISSUES.md` and the branch's `dev/features/<name>.md` if it exists.
4. Run `uv run pytest -q` to confirm the branch state before continuing.
5. If the branch is merged but its docs are not updated, finish the docs task before starting the next branch.

## Open questions for the user

Answer these before the branch that needs them starts. Each has a recommended default.

- **Q1 (A):** `task_accept` and `task_reject` also return `{"ok": false}` for an unknown id. Should they raise the same not-found error? Recommended: yes. `ok: false` then means only "the task is not completed". (Answered 2026-11-14: the user approved the recommendation.)
- **Q2 (C):** Should `""` clear `due`, `remind_at`, or `end`? Recommended: yes. Today `""` is stored and counts as permanently overdue, and no tool can clear a field. The alternative is to reject `""` as an unparseable time. (Answered 2026-11-14: the user approved the recommendation.)
- **Q3 (C):** Normalizing requires parsing. Should an unparseable time (such as `"next tuesday"`) be rejected with an error? Recommended: yes. Today such a value is stored and never comes due. (Answered 2026-11-14: the user approved the recommendation.)
- **Q4 (B):** Should only newly created databases get folder mode 700 and file mode 600? Recommended: yes. The live database already has those modes from the db-move runbook. Changing modes on an existing file at startup is out of scope. (Answered 2026-11-14: the user approved the recommendation.)
- **Q5 (item 8):** Should editing a reviewed task's content clear `reviewed` (`docs/ISSUES.md`, Planned)? Recommended: defer. No branch in this plan changes it. (Answered 2026-11-14: the user approved the recommendation.)
- **Q6 (E):** One promote after all four branches, or restart the clients now to finish the list-truncation checks? Recommended: one promote at the end. (Answered 2026-11-14: the user approved one promote at the end.)
- **Q7 (before Branch A):** The repo is public. Commit this plan file, or gitignore `docs/superpowers/plans/`? Recommended: commit it. It holds no personal data, and the feature docs are already committed. Settle this first: while the file is untracked, the new `promote.sh` guard refuses to run (Task D3 Step 4, Task E2). (Answered 2026-11-14: the user approved committing it.)

---

## Branch A: `unknown-id-errors` (item 1)

### Design

**Problem.** `crud.update` and `crud.delete` return `cur.rowcount > 0` (`src/fleetcom/crud.py:62`, `:68`). An unknown id and an update with no recognized fields both give `{"ok": false}`. A Hermes caller spent two calls on a task stored in a different database because of this (`docs/ISSUES.md`, Bugs).

**Change.**

- Add `class NotFoundError(ValueError)` to `crud.py`. Because it subclasses `ValueError`, `server._anticipated` already turns it into a `ToolError`, and no server change is needed for the error path.
- `crud.update` raises `NotFoundError` when the `UPDATE` matches no row. With no fields, it checks that the row exists, raises if not, and otherwise returns `False`.
- `crud.delete` raises `NotFoundError` when the `DELETE` matches no row, and otherwise returns `True`.
- The message is `f"{table}: no row with id {id_!r}"`, for example `tasks: no row with id 'abc'`. `repr` quotes the caller's text, so stored or injected text cannot pose as part of the message.
- If Q1 is approved: `tasks.accept` and `tasks.reject` raise the same error when no row has the id. A row that exists but is not `completed` still returns `False`.

**After the change**, `{"ok": false}` from an update means only "nothing to change". A delete never returns `ok: false`.

**Rejected:** a structured `{"ok": false, "reason": "not_found"}` (decision of 2026-11-14 in `docs/ISSUES.md`).

**Interface change.** Six tools now error on an unknown id; two more if Q1 is approved. Pre-1.0, no deprecation period (`dev/IMPLEMENTATION-SPEC.md`, Deprecation Policy).

### Task A1: Design doc and test plan

**Files:**
- Create: `dev/features/unknown-id-errors.md`, `dev/features/unknown-id-errors-tests.md`

- [x] **Step 1:** Run `git switch -c unknown-id-errors` from an up-to-date `main`.
- [x] **Step 2:** Run `uv run pytest -q`, `uv run ruff check`, and `uv run ruff format --check`. Record the baseline in the test plan.
- [x] **Step 3:** Load the `maintaining-dev-docs` skill. Write the design doc from the Design section above, with the answer to Q1.
- [x] **Step 4:** Write the test plan with the cases from Task A2 and the live check from Task E3.
- [x] **Step 5:** Review the test plan with the user. Do not continue until the user confirms it.
- [x] **Step 6:** Commit both docs on the branch.

### Task A2: Not-found errors in `crud` and the tools

**Files:**
- Modify: `src/fleetcom/crud.py`
- Modify: `src/fleetcom/tasks.py` (only if Q1 is approved)
- Modify: `src/fleetcom/server.py` (docstrings only)
- Test: `tests/test_tasks.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `crud.NotFoundError(ValueError)`. `crud.update(...) -> bool` returns `True` when a row changed and `False` for no fields on an existing row. `crud.delete(...) -> bool` returns `True` or raises.

- [x] **Step 1: Write the failing tests.** In `tests/test_tasks.py`, replace `test_update_nonexistent_id_returns_false` and the last line of `test_delete_removes_row`:

```python
from fleetcom import crud


def test_update_nonexistent_id_raises_not_found(conn):
    with pytest.raises(crud.NotFoundError, match="no-such-id"):
        tasks.update(conn, "no-such-id", status="completed")


def test_update_with_no_fields_on_unknown_id_raises_not_found(conn):
    with pytest.raises(crud.NotFoundError, match="no-such-id"):
        tasks.update(conn, "no-such-id")


def test_update_with_no_fields_on_existing_id_returns_false(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="a")
    assert tasks.update(conn, task_id) is False


def test_delete_removes_row(conn):
    task_id = tasks.create(conn, created_by="agent-1", summary="a")
    assert tasks.delete(conn, task_id) is True
    assert tasks.get(conn, task_id) is None
    with pytest.raises(crud.NotFoundError, match=task_id):
        tasks.delete(conn, task_id)
```

In `tests/test_server.py`, add one test across all six tools:

```python
@pytest.mark.parametrize(
    "tool, args",
    [
        ("task_update", {"task_id": "missing-1", "status": "open"}),
        ("task_delete", {"task_id": "missing-1"}),
        ("event_update", {"event_id": "missing-1", "summary": "x"}),
        ("event_delete", {"event_id": "missing-1"}),
        ("contact_update", {"contact_id": "missing-1", "name": "x"}),
        ("contact_delete", {"contact_id": "missing-1"}),
    ],
)
async def test_unknown_id_is_an_error_naming_the_id(server, tool, args):
    async with Client(server) as client:
        res = await asyncio.wait_for(client.call_tool(tool, args), timeout=10)
    assert res.is_error is True
    assert "missing-1" in res.content[0].text
```

If Q1 is approved, add `("task_accept", {"task_id": "missing-1", "actor": "cos"})` and `("task_reject", {"task_id": "missing-1", "actor": "cos", "note": "n"})` to the list. Keep the existing assertion at `tests/test_server.py:149` (`ok` is `False` for a task that is not completed).

- [x] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest tests/test_tasks.py tests/test_server.py -q`. Expected: the new tests fail with `ok: false` results instead of errors. `test_update_with_no_fields_on_existing_id_returns_false` passes before and after; it guards the one remaining `ok: false` case.

- [x] **Step 3: Implement.** In `src/fleetcom/crud.py`:

```python
class NotFoundError(ValueError):
    """An update or delete named an id that no row has."""


def _not_found(table: str, id_: str) -> NotFoundError:
    return NotFoundError(f"{table}: no row with id {id_!r}")


def update(
    conn: sqlite3.Connection, table: str, allowed: set[str], id_: str, **fields
) -> bool:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown field(s) for {table}: {sorted(unknown)}")
    if not fields:
        if get(conn, table, id_) is None:
            raise _not_found(table, id_)
        return False
    fields["updated_at"] = util.now_iso()
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    args = [*fields.values(), id_]
    with conn:
        cur = conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", args)
    if cur.rowcount == 0:
        raise _not_found(table, id_)
    return True


def delete(conn: sqlite3.Connection, table: str, id_: str) -> bool:
    with conn:
        cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (id_,))
    if cur.rowcount == 0:
        raise _not_found(table, id_)
    return True
```

If Q1 is approved, in `src/fleetcom/tasks.py` `accept` and `reject`, replace `return cur.rowcount > 0` with:

```python
    if cur.rowcount == 0 and get(conn, task_id) is None:
        raise crud.NotFoundError(f"{TABLE}: no row with id {task_id!r}")
    return cur.rowcount > 0
```

- [x] **Step 4: Update the tool docstrings** in `src/fleetcom/server.py`. Add one sentence to each of the six update and delete tools: "An unknown id is an error that names the id." For `task_update`, `event_update`, and `contact_update`, also say: "ok=false means no argument changed anything." If Q1 is approved, change "No-op (ok=False) unless the task is currently completed" in `task_accept` and `task_reject` to "ok=false means the task is not completed; an unknown id is an error."

- [x] **Step 5: Run the full suite.** Run `uv run pytest -q`, `uv run ruff check`, and `uv run ruff format --check`. Expected: all pass. Fix any other test that asserted `False` for an unknown id.

- [x] **Step 6: Commit** `src/fleetcom/crud.py`, `src/fleetcom/server.py`, `tests/test_tasks.py`, `tests/test_server.py`, and `src/fleetcom/tasks.py` if changed.

### Task A3: Docs and merge

**Files:**
- Modify: `src/skills/fleetcom/SKILL.md`, `src/skills/fleetcom/references/tools.md`, `CHANGELOG.md`, `dev/CODEMAP.md` (crud row), `dev/SKELETON.md` (`_anticipated` paragraph), `docs/ISSUES.md`, the feature's design and test docs.

- [x] **Step 1:** Add to `SKILL.md` Task conventions: "An update or delete with an unknown id is an error that names the id. If you see one, check that you are on the live database before retrying."
- [x] **Step 2:** Add the same rule to the top of `references/tools.md`.
- [x] **Step 3:** Add to `CHANGELOG.md`: "Change update and delete tools to return an error naming the id when no row has it."
- [x] **Step 4:** Update the crud row in `dev/CODEMAP.md` and the `_anticipated` paragraph in `dev/SKELETON.md` to name `NotFoundError`.
- [x] **Step 5:** Mark the unknown-id bug resolved in `docs/ISSUES.md`, citing the branch.
- [x] **Step 6:** Dispatch a reviewer subagent (role "Code review before a merge"). Record its findings and resolutions in `unknown-id-errors-tests.md`.
- [x] **Step 7:** Commit the docs. Ask the user to approve the merge. After the merge, run the tests and linters on `main`.

---

## Branch B: `db-open-safety` (items 3, 7, and file modes from 8)

### Design

**Problem 1, missing database (item 3).** `db.connect` creates the parent folder and the file for any path (`src/fleetcom/db.py:93-103`). A mistyped `--db` or `FLEETCOM_DB_PATH` silently gives an empty database. `~` is not expanded, so `--db ~/x.db` from a config that does not run a shell creates a folder literally named `~`.

**Problem 2, file modes (item 8).** A database created through `db.connect` gets folder mode 755 and file mode 644 under umask 022, although it can hold personal data.

**Problem 3, lock errors (item 7).** `_anticipated` does not catch `sqlite3.OperationalError`, so `database is locked` reaches the caller as "Error executing tool X" with no reason. `db.migrate` writes `schema_version` on every startup, so a write lock held past the busy timeout crashes server startup.

**Change.**

- `db.connect(path, *, create=False)`:
  - Expand `~` with `Path(path).expanduser()`.
  - With `create=False`, raise `FileNotFoundError(f"database not found: {file} (pass --create-db to create it)")` if the file does not exist. Then open with the URI `file:<absolute path>?mode=rw`, so SQLite itself refuses to create a file that disappears between the check and the open.
  - With `create=True`, create a missing parent folder with mode 700, create a missing file with mode 600 (`file.touch(mode=0o600, exist_ok=True)`), and open with `mode=rwc`. SQLite gives the `-wal` and `-shm` files the main file's mode (inferred from SQLite's unix VFS documentation; Task B2 Step 1 tests it).
  - An existing file opens the same way with either value of `create`.
- `server._parse_args(argv=None) -> argparse.Namespace` replaces `_resolve_db_path`. It adds `--create-db` (`store_true`) and fills `args.db` from `--db`, then `FLEETCOM_DB_PATH`, then the default.
- `server.main` catches `FileNotFoundError` from `db.connect` and exits with `sys.exit(f"fleetcom-mcp: {error}")`, which prints to stderr and exits with status 1. The MCP client then reports that the server failed to start. It also catches `sqlite3.OperationalError` from `db.connect` and exits with `fleetcom-mcp: cannot open database {path}: {error}`; `--db ~/.fleetcom` (a folder) takes that path.
- `_anticipated` also catches `sqlite3.OperationalError` whose message contains `locked`, and raises `ToolError("database is locked: another fleetcom server held the write lock past the busy timeout; retry the call")`. Other `OperationalError`s propagate unchanged.
- `db.migrate` reads `schema_version` first and returns without writing when the stored version equals `SCHEMA_VERSION`. A database with no `schema_version` table (a new file) runs the DDL and the stamp as today.

**Deploy impact.** Every client config already passes `--db` with the absolute path of the live database (db-move cutover, 2026-11-01), so no config needs `--create-db`. The user or hermes-manager confirms this before Task E2, because those configs are outside this repo.

**Rejected:**
- Keeping silent auto-create (decision of 2026-11-14).
- Creating a missing file only for the default path: the default path is a mistake too when the live database is elsewhere.
- Changing modes on an existing database at startup (Q4).

### Task B1: Design doc and test plan

**Files:**
- Create: `dev/features/db-open-safety.md`, `dev/features/db-open-safety-tests.md`

- [x] **Step 1:** Run `git switch -c db-open-safety` from an up-to-date `main`.
- [x] **Step 2:** Run the tests and linters and record the baseline.
- [x] **Step 3:** Load `maintaining-dev-docs`. Write the design doc from the Design section above, with the answer to Q4.
- [x] **Step 4:** Write the test plan with the cases from Tasks B2 to B4 and the live checks from Task E3.
- [x] **Step 5:** Review the test plan with the user. Do not continue until the user confirms it.
- [x] **Step 6:** Commit both docs on the branch.

### Task B2: `db.connect` refuses a missing file unless asked to create it

**Files:**
- Modify: `src/fleetcom/db.py`
- Modify: `tests/conftest.py`, `tests/test_db.py`, `tests/test_tasks.py`, `tests/test_server.py`, `tests/test_list_truncation.py` (every `db.connect` on a new file passes `create=True`)
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `db.connect(path: str, *, create: bool = False) -> sqlite3.Connection`. Raises `FileNotFoundError` for a missing file when `create` is false.

- [x] **Step 1: Write the failing tests** in `tests/test_db.py`:

```python
import stat


def test_connect_refuses_a_missing_file(tmp_path):
    path = tmp_path / "missing" / "fleetcom.db"
    with pytest.raises(FileNotFoundError, match="--create-db"):
        db.connect(str(path))
    assert not path.parent.exists()


def test_connect_creates_a_private_file_when_asked(tmp_path):
    path = tmp_path / "new" / "fleetcom.db"
    conn = db.connect(str(path), create=True)
    db.migrate(conn)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(f"{path}-wal").stat().st_mode) == 0o600
    conn.close()


def test_connect_opens_an_existing_file_without_create(tmp_path):
    path = tmp_path / "fleetcom.db"
    db.migrate(db.connect(str(path), create=True))
    conn = db.connect(str(path))
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    conn.close()


def test_connect_expands_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    conn = db.connect("~/fleetcom.db", create=True)
    conn.close()
    assert (tmp_path / "fleetcom.db").exists()
    assert not (tmp_path / "~").exists()
```

Add `from pathlib import Path` to the imports if it is missing.

- [x] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest tests/test_db.py -q`. Expected: `TypeError` for the unknown `create` argument, and the missing-file test fails because a file is created.

- [x] **Step 3: Implement** in `src/fleetcom/db.py`:

```python
def connect(path: str, *, create: bool = False) -> sqlite3.Connection:
    """Open the SQLite DB at path with the required PRAGMAs.

    Only create=True makes a new file, so a mistyped path fails instead of
    starting an empty database.
    """
    file = Path(path).expanduser()
    if create:
        file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        file.touch(mode=0o600, exist_ok=True)
    elif not file.exists():
        raise FileNotFoundError(
            f"database not found: {file} (pass --create-db to create it)"
        )
    uri = f"{file.resolve().as_uri()}?mode=rw"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _enable_wal(conn)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

`touch` creates the file, so `mode=rw` is enough in both cases.

- [x] **Step 4: Update the call sites on new files.** Pass `create=True` in `tests/conftest.py:8`, `tests/test_server.py:12` and `:233`, `tests/test_db.py:101`, `:114`, `:123`, and `:129` (`_open_at_barrier`, which six processes call on one new file), `tests/test_tasks.py:149` (the first open of `shared.db`), and every `db.connect` in `tests/test_list_truncation.py`. Leave `tests/test_tasks.py:151` without it, because the file exists by then. Run `grep -n "db.connect" tests/` to confirm none is missed.

- [x] **Step 5: Run the full suite.** Expected: all pass, including `test_servers_starting_together_on_a_new_file_all_succeed`, which now runs six concurrent `touch` calls with `exist_ok=True`.

- [x] **Step 6: Commit** `src/fleetcom/db.py` and the changed test files.

### Task B3: `--create-db` flag and a clean exit for a missing file

**Files:**
- Modify: `src/fleetcom/server.py` (`_resolve_db_path` becomes `_parse_args`; `main`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `db.connect(path, *, create)` from Task B2.
- Produces: `server._parse_args(argv: list[str] | None = None) -> argparse.Namespace` with `db: str` and `create_db: bool`. Task D2 adds `--version` here.

- [x] **Step 1: Write the failing tests.** Replace `tests/test_cli.py` with:

```python
import pytest

from fleetcom import server
from fleetcom.server import _parse_args


def test_db_flag_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FLEETCOM_DB_PATH", str(tmp_path / "env.db"))
    flag_path = str(tmp_path / "flag.db")
    assert _parse_args(["--db", flag_path]).db == flag_path


def test_db_falls_back_to_env_when_no_flag(monkeypatch, tmp_path):
    env_path = str(tmp_path / "env.db")
    monkeypatch.setenv("FLEETCOM_DB_PATH", env_path)
    assert _parse_args([]).db == env_path


def test_create_db_defaults_to_false():
    assert _parse_args([]).create_db is False
    assert _parse_args(["--create-db"]).create_db is True


def test_main_exits_with_a_message_for_a_missing_database(monkeypatch, tmp_path):
    missing = tmp_path / "missing.db"
    monkeypatch.setattr("sys.argv", ["fleetcom-mcp", "--db", str(missing)])
    with pytest.raises(SystemExit) as exit_info:
        server.main()
    assert "--create-db" in str(exit_info.value.code)
    assert not missing.exists()


def test_main_exits_with_a_message_for_a_folder_path(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["fleetcom-mcp", "--db", str(tmp_path)])
    with pytest.raises(SystemExit) as exit_info:
        server.main()
    assert "cannot open database" in str(exit_info.value.code)
```

- [x] **Step 2: Run the tests and confirm they fail.** Run `uv run pytest tests/test_cli.py -q`. Expected: `ImportError` for `_parse_args`.

- [x] **Step 3: Implement** in `src/fleetcom/server.py`. Add `import sys` to the imports. Replace `_resolve_db_path` and `main`:

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fleetcom-mcp")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the fleetcom SQLite database (overrides FLEETCOM_DB_PATH)",
    )
    parser.add_argument(
        "--create-db",
        action="store_true",
        help="Create the database if it does not exist",
    )
    args = parser.parse_args(argv)
    args.db = args.db or db.default_db_path()
    return args


def main() -> None:
    args = _parse_args()
    try:
        conn = db.connect(args.db, create=args.create_db)
    except FileNotFoundError as error:
        sys.exit(f"fleetcom-mcp: {error}")
    except sqlite3.OperationalError as error:
        sys.exit(f"fleetcom-mcp: cannot open database {args.db}: {error}")
    db.migrate(conn)
    server = build_server(conn)
    server.run(transport="stdio")
```

- [x] **Step 4: Run the full suite and linters.** Expected: all pass.

- [x] **Step 5: Commit** `src/fleetcom/server.py` and `tests/test_cli.py`.

### Task B4: Lock errors reach the caller; startup does not write when current

**Files:**
- Modify: `src/fleetcom/server.py` (`_anticipated`), `src/fleetcom/db.py` (`migrate`)
- Test: `tests/test_server.py`, `tests/test_db.py`

**Interfaces:**
- Produces: `db.migrate(conn) -> None` that writes nothing on a database already at `SCHEMA_VERSION`. Branch C calls a repair step after it in `server.main`.

- [x] **Step 1: Write the failing tests.** In `tests/test_server.py`:

```python
import sqlite3


async def test_a_locked_database_is_a_tool_error_with_a_reason(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    conn = db.connect(path, create=True)
    db.migrate(conn)
    conn.execute("PRAGMA busy_timeout = 0")
    holder = sqlite3.connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        async with Client(build_server(conn)) as client:
            res = await asyncio.wait_for(
                client.call_tool("task_create", {"summary": "x", "created_by": "a"}),
                timeout=10,
            )
        assert res.is_error is True
        assert "locked" in res.content[0].text
        assert "retry" in res.content[0].text
    finally:
        holder.rollback()
        holder.close()
        conn.close()
```

In `tests/test_db.py`:

```python
def test_migrate_does_not_write_when_the_schema_is_current(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    db.migrate(db.connect(path, create=True))
    conn = db.connect(path)
    conn.execute("PRAGMA busy_timeout = 0")
    holder = sqlite3.connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        db.migrate(conn)
    finally:
        holder.rollback()
        holder.close()
        conn.close()
```

- [x] **Step 2: Run the tests and confirm they fail.** Expected: the first fails with the generic "Error executing tool task_create" text, and the second raises `sqlite3.OperationalError: database is locked`.

- [x] **Step 3: Implement.** In `_anticipated`, add a clause after the existing one:

```python
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc):
                    raise
                raise ToolError(
                    "database is locked: another fleetcom server held the write "
                    "lock past the busy timeout; retry the call"
                ) from exc
```

In `src/fleetcom/db.py`:

```python
def _stored_version(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return None
    return row[0] if row else None


def migrate(conn: sqlite3.Connection) -> None:
    """Create all tables and record the schema version, unless already current.

    Writing on every startup would crash startup whenever another server holds
    the write lock past the busy timeout.
    """
    if _stored_version(conn) == SCHEMA_VERSION:
        return
    conn.executescript(SCHEMA_DDL)
    conn.execute(
        "INSERT INTO schema_version (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version = excluded.version",
        (SCHEMA_VERSION,),
    )
    conn.commit()
```

- [x] **Step 4: Run the full suite and linters.** Expected: all pass, including `test_migrate_is_idempotent`.

- [x] **Step 5: Commit** the four changed files.

### Task B5: Docs and merge

**Files:**
- Modify: `README.md` (configuration section), `src/skills/fleetcom/SKILL.md` (Wiring notes), `CHANGELOG.md`, `dev/CODEMAP.md` (db and server rows), `dev/SKELETON.md` (Logic Flow first bullet; the WAL-retry invariant), `dev/IMPLEMENTATION-SPEC.md` (Config Reference), `docs/ISSUES.md`, the feature's docs.

- [x] **Step 1:** Add `--create-db` to the Config Reference table and to the README configuration section. State that a missing database is an error without it.
- [x] **Step 2:** In `SKILL.md` Wiring notes, add: "A missing database file is a startup error. Pass `--create-db` only when setting up a new database."
- [x] **Step 3:** Add to `CHANGELOG.md`: "Change a missing database file to a startup error unless `--create-db` is passed; expand `~` in database paths." "Create new database files with mode 600 in a mode 700 folder." "Report `database is locked` as a tool error that says to retry." "Stop writing `schema_version` on every startup."
- [x] **Step 4:** Update `dev/SKELETON.md` and `dev/CODEMAP.md` for `connect(create=)`, `_parse_args`, and `migrate`.
- [x] **Step 5:** Mark resolved in `docs/ISSUES.md`: the wrong-`--db` item, the lock item, and the file-mode item.
- [x] **Step 6:** Dispatch a reviewer subagent ("Code review before a merge"). Record findings in `db-open-safety-tests.md`.
- [x] **Step 7:** Commit the docs. Ask the user to approve the merge. After the merge, run the tests and linters on `main`.

---

## Branch C: `utc-timestamps` (item 2, and `due=""` from item 8)

### Design

**Problem.** `tasks.list(due_now=True)` compares `due` and `remind_at` with `now_iso()` as strings (`src/fleetcom/tasks.py:80-84`). `2026-11-02T09:00:00-08:00` sorts as 09:00 UTC, not 17:00 UTC, so a negative offset flags a task early by the offset's size. A read-only count on 2026-11-02 found 29 tasks with a non-UTC `due` or `remind_at`, 23 of them active, and no non-UTC events. Separately, `due=""` sorts before every time and counts as permanently overdue, and no tool can clear a field.

**Change.**

- Add `util.to_utc(value: str | None) -> str | None`:
  - `None` returns `None`.
  - `""` returns `None` if Q2 is approved; otherwise it raises `ValueError`.
  - Parse with `datetime.fromisoformat` (Python 3.11 accepts `Z`, offsets, fractional seconds, date-only, and a space separator; checked on 2026-11-14).
  - A value without an offset is read as UTC, which keeps its meaning under today's string comparison. A date-only value becomes midnight UTC.
  - Return `now_iso()`'s format, `%Y-%m-%dT%H:%M:%SZ`. Fractional seconds are dropped.
  - An unparseable value raises `ValueError(f"not an ISO-8601 time: {value!r}")` (Q3). So does a value that parses but cannot convert to UTC, such as `0001-01-01T00:00:00+05:00`, which raises `OverflowError` in `astimezone`. Without this, one such stored row would stop every new server at startup.
- Add `util.normalize_times(fields: dict, names: tuple[str, ...]) -> dict`, which returns a copy with each present name passed through `to_utc` and the field name prefixed to any error message.
- Apply it on every write and every range query:
  - `tasks.create` and `tasks.update`: `due`, `remind_at`.
  - `events.create` and `events.update`: `start`, `end`.
  - `events.list_in_range`: the `start` and `end` bounds.
- Because `server._updated_fields` drops `None` but passes `""`, `task_update(due="")` reaches `tasks.update` as `due=""`, becomes `due=None`, and `crud.update` sets the column to `NULL`. That is the clearing path. `start` is `NOT NULL`, so `event_update(start="")` fails on the constraint and reaches the caller as a `ToolError`.
- **Existing rows.** Add `db.normalize_stored_times(conn) -> int`, and call it in `server.main` after `db.migrate`:
  - For each table and its time columns (`tasks`: `due`, `remind_at`; `events`: `start`, `end`, as module literals), select the rows where any time column is not null and does not match `GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z'`. This is a read, so a current database costs no write at startup.
  - Normalize all of a row's time columns in one `UPDATE ... WHERE id = ? AND <each column> IS <old value>`, inside one `with conn:` block. One statement per row matters for events: normalizing `start` alone can briefly break `CHECK (end IS NULL OR end >= start)`.
  - Skip a value that `to_utc` cannot parse, and skip a row whose `UPDATE` raises `IntegrityError`. Leave both for a person, and count them.
  - If the write raises `OperationalError` for `locked`, skip the repair; the next startup retries it. Startup never fails because of the repair.
  - Do not change `updated_at`, because the content did not change.
  - Print `fleetcom-mcp: normalized times in N rows to UTC; left M values` to stderr when either count is non-zero. The MCP stdio channel is stdout, so stderr is safe.
- The repair runs at every startup, so rows written by an old server that has not restarted yet are fixed by the next new server.

**Rejected:**
- Rejecting non-UTC values (decision of 2026-11-14).
- A one-time script run by hand: an old server still running can write offset values after the script, and nothing would fix them.
- Comparing with SQLite `datetime()` in the query instead of normalizing: leaves the stored strings inconsistent for every reader and does not fix the events `CHECK`.
- A `schema_version` bump that runs the repair once: same gap as the one-time script.

### Task C1: Design doc and test plan

**Files:**
- Create: `dev/features/utc-timestamps.md`, `dev/features/utc-timestamps-tests.md`

- [x] **Step 1:** Run `git switch -c utc-timestamps` from an up-to-date `main` that includes Branch B.
- [x] **Step 2:** Run the tests and linters and record the baseline.
- [x] **Step 3:** With the user's go-ahead, run a read-only count on the live database: rows per table and column that fail the GLOB above, and how many of those `to_utc` cannot parse. Open it with `sqlite3 "file:$HOME/.fleetcom/fleetcom.db?mode=ro" -cmd ".timeout 5000"`. Record the counts, not the values, in the design doc.
- [x] **Step 4:** Load `maintaining-dev-docs`. Write the design doc from the Design section above, with the answers to Q2 and Q3.
- [x] **Step 5:** Write the test plan with the cases from Tasks C2 to C4 and the live checks from Task E3.
- [x] **Step 6:** Review the test plan with the user. Do not continue until the user confirms it.
- [x] **Step 7:** Commit both docs on the branch.

### Task C2: `util.to_utc` and `util.normalize_times`

**Files:**
- Modify: `src/fleetcom/util.py`
- Test: `tests/test_util.py` (new; the first unit tests for `util`)

**Interfaces:**
- Produces: `util.to_utc(value: str | None) -> str | None`; `util.normalize_times(fields: dict, names: tuple[str, ...]) -> dict`. Both raise `ValueError` for an unparseable value.

- [x] **Step 1: Write the failing tests** in `tests/test_util.py`:

```python
import pytest

from fleetcom import util


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-11-02T09:00:00-08:00", "2026-11-02T17:00:00Z"),
        ("2026-11-02T23:30:00-08:00", "2026-11-03T07:30:00Z"),
        ("2026-11-02T09:00:00+05:30", "2026-11-02T03:30:00Z"),
        ("2026-11-02T09:00:00Z", "2026-11-02T09:00:00Z"),
        ("2026-11-02T09:00:00", "2026-11-02T09:00:00Z"),
        ("2026-11-02 09:00", "2026-11-02T09:00:00Z"),
        ("2026-11-02", "2026-11-02T00:00:00Z"),
        ("2026-11-02T09:00:00.999+00:00", "2026-11-02T09:00:00Z"),
        (None, None),
    ],
)
def test_to_utc(value, expected):
    assert util.to_utc(value) == expected


def test_to_utc_clears_on_empty_string():
    assert util.to_utc("") is None


@pytest.mark.parametrize("value", ["next tuesday", "0001-01-01T00:00:00+05:00"])
def test_to_utc_rejects_a_value_it_cannot_convert(value):
    with pytest.raises(ValueError, match="ISO-8601"):
        util.to_utc(value)


def test_normalize_times_touches_only_named_fields():
    fields = {
        "due": "2026-11-02T09:00:00-08:00",
        "summary": "2026-11-02T09:00:00-08:00",
    }
    assert util.normalize_times(fields, ("due", "remind_at")) == {
        "due": "2026-11-02T17:00:00Z",
        "summary": "2026-11-02T09:00:00-08:00",
    }


def test_normalize_times_names_the_field_in_errors():
    with pytest.raises(ValueError, match="remind_at"):
        util.normalize_times({"remind_at": "soon"}, ("due", "remind_at"))
```

If Q2 is not approved, replace `test_to_utc_clears_on_empty_string` with a test that `""` raises `ValueError`.

- [x] **Step 2: Run and confirm failure.** Run `uv run pytest tests/test_util.py -q`. Expected: `AttributeError` for `to_utc`.

- [x] **Step 3: Implement** in `src/fleetcom/util.py`:

```python
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


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
```

If Q2 is not approved, drop `or value == ""` so `""` fails to parse.

- [x] **Step 4: Run the tests.** Expected: all pass.
- [x] **Step 5: Commit** `src/fleetcom/util.py` and `tests/test_util.py`.

### Task C3: Normalize on every write and range query

**Files:**
- Modify: `src/fleetcom/tasks.py`, `src/fleetcom/events.py`, `src/fleetcom/server.py` (docstrings)
- Test: `tests/test_tasks.py`, `tests/test_events.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `util.normalize_times`, `util.to_utc` from Task C2.
- Produces: module constants `tasks.TIME_FIELDS = ("due", "remind_at")` and `events.TIME_FIELDS = ("start", "end")`, which Task C4 reuses.

- [x] **Step 1: Write the failing tests.** In `tests/test_tasks.py`:

```python
from datetime import UTC, datetime, timedelta, timezone

PACIFIC = timezone(timedelta(hours=-8))


def test_create_stores_due_and_remind_at_in_utc(conn):
    task_id = tasks.create(
        conn,
        created_by="a",
        summary="x",
        due="2026-11-02T09:00:00-08:00",
        remind_at="2026-11-02",
    )
    row = tasks.get(conn, task_id)
    assert row["due"] == "2026-11-02T17:00:00Z"
    assert row["remind_at"] == "2026-11-02T00:00:00Z"


def test_due_now_does_not_flag_an_offset_due_early(conn):
    later = datetime.now(UTC) + timedelta(hours=4)
    due = later.astimezone(PACIFIC).isoformat(timespec="seconds")
    task_id = tasks.create(conn, created_by="a", summary="x", due=due)
    assert task_id not in [t["id"] for t in tasks.list(conn, due_now=True)]


def test_update_with_empty_string_clears_due(conn):
    task_id = tasks.create(
        conn, created_by="a", summary="x", due="2000-01-01T00:00:00Z"
    )
    tasks.update(conn, task_id, due="")
    assert tasks.get(conn, task_id)["due"] is None
    assert task_id not in [t["id"] for t in tasks.list(conn, due_now=True)]


def test_create_rejects_an_unparseable_due(conn):
    with pytest.raises(ValueError, match="due"):
        tasks.create(conn, created_by="a", summary="x", due="next tuesday")
```

In `tests/test_events.py`:

```python
def test_event_times_are_stored_in_utc(conn):
    event_id = events.create(
        conn,
        created_by="a",
        summary="x",
        start="2026-11-02T09:00:00-08:00",
        end="2026-11-02T10:00:00-08:00",
    )
    row = events.get(conn, event_id)
    assert (row["start"], row["end"]) == (
        "2026-11-02T17:00:00Z",
        "2026-11-02T18:00:00Z",
    )


def test_list_in_range_normalizes_its_bounds(conn):
    event_id = events.create(
        conn, created_by="a", summary="x", start="2026-11-02T17:30:00Z"
    )
    rows = events.list_in_range(
        conn, start="2026-11-02T09:00:00-08:00", end="2026-11-02T10:00:00-08:00"
    )
    assert [r["id"] for r in rows] == [event_id]
```

In `tests/test_server.py`, check that a bad time reaches the caller with its reason:

```python
async def test_an_unparseable_time_is_a_tool_error_naming_the_field(server):
    async with Client(server) as client:
        res = await asyncio.wait_for(
            client.call_tool(
                "task_create", {"summary": "x", "created_by": "a", "remind_at": "soon"}
            ),
            timeout=10,
        )
    assert res.is_error is True
    assert "remind_at" in res.content[0].text
```

If Q2 is not approved, replace `test_update_with_empty_string_clears_due` with a test that `due=""` raises `ValueError`.

- [x] **Step 2: Run and confirm failure.** Run `uv run pytest tests/test_tasks.py tests/test_events.py tests/test_server.py -q`. Expected: stored values keep their offsets, the offset task appears in `due_now`, and no error is raised for `"soon"`.

- [x] **Step 3: Implement.** In `src/fleetcom/tasks.py`, add `TIME_FIELDS = ("due", "remind_at")`. In `create`, pass `**util.normalize_times({"due": due, "remind_at": remind_at}, TIME_FIELDS)` in place of the two arguments. At the top of `update`, add `fields = util.normalize_times(fields, TIME_FIELDS)`.

In `src/fleetcom/events.py`, add `TIME_FIELDS = ("start", "end")`. In `create`, pass `**util.normalize_times({"start": start, "end": end}, TIME_FIELDS)`. At the top of `update`, add `fields = util.normalize_times(fields, TIME_FIELDS)`. At the top of `list_in_range`, add `start, end = util.to_utc(start), util.to_utc(end)`.

- [x] **Step 4: Update the tool docstrings** in `server.py`. For `task_create` and `task_update`: "Times are ISO-8601; fleetcom stores them in UTC, reads a time without an offset as UTC, and rejects anything it cannot parse." For `task_update`, if Q2 is approved: "due='' or remind_at='' clears the field." For `event_create`, `event_update`, and `event_list`, add the same storage sentence.

- [x] **Step 5: Run the full suite and linters.** Expected: all pass. A list-truncation test that inserts raw times through SQL is unaffected, because only the entity functions normalize.

- [x] **Step 6: Commit** the changed source and test files.

### Task C4: Repair stored rows at startup

**Files:**
- Modify: `src/fleetcom/db.py`, `src/fleetcom/server.py` (`main`)
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `util.to_utc`; `tasks.TIME_FIELDS`, `events.TIME_FIELDS` are restated as literals in `db.py`, because `db` must not import the entity modules.
- Produces: `db.normalize_stored_times(conn) -> tuple[int, int]`, returning (rows fixed, values left).

- [x] **Step 1: Write the failing tests** in `tests/test_db.py`:

```python
def _raw_task(conn, id_, due=None, remind_at=None):
    with conn:
        conn.execute(
            "INSERT INTO tasks (id, summary, created_by, created_at, updated_at, due, remind_at) "
            "VALUES (?, 'x', 'a', 't', 't', ?, ?)",
            (id_, due, remind_at),
        )


def test_normalize_stored_times_fixes_offsets_and_blanks(conn):
    _raw_task(conn, "t1", due="2026-11-02T09:00:00-08:00")
    _raw_task(conn, "t2", remind_at="")
    _raw_task(conn, "t3", due="2026-11-02T09:00:00Z")
    _raw_task(conn, "t4", due="next tuesday")
    with conn:
        conn.execute(
            "INSERT INTO events (id, summary, start, end, created_by, created_at, updated_at) "
            "VALUES ('e1', 'x', '2026-11-02T09:00:00-08:00', '2026-11-02T10:00:00-08:00', 'a', 't', 't')"
        )

    assert db.normalize_stored_times(conn) == (3, 1)

    def value(table, column, id_):
        return conn.execute(
            f"SELECT {column} FROM {table} WHERE id = ?", (id_,)
        ).fetchone()[0]

    assert value("tasks", "due", "t1") == "2026-11-02T17:00:00Z"
    assert value("tasks", "remind_at", "t2") is None
    assert value("tasks", "due", "t4") == "next tuesday"
    assert value("tasks", "updated_at", "t1") == "t"
    assert (value("events", "start", "e1"), value("events", "end", "e1")) == (
        "2026-11-02T17:00:00Z",
        "2026-11-02T18:00:00Z",
    )


def test_normalize_stored_times_writes_nothing_when_clean(conn):
    _raw_task(conn, "t1", due="2026-11-02T09:00:00Z")
    assert db.normalize_stored_times(conn) == (0, 0)


def test_normalize_stored_times_skips_when_locked(tmp_path):
    path = str(tmp_path / "fleetcom.db")
    conn = db.connect(path, create=True)
    db.migrate(conn)
    _raw_task(conn, "t1", due="2026-11-02T09:00:00-08:00")
    conn.execute("PRAGMA busy_timeout = 0")
    holder = sqlite3.connect(path)
    holder.execute("BEGIN IMMEDIATE")
    try:
        assert db.normalize_stored_times(conn) == (0, 0)
    finally:
        holder.rollback()
        holder.close()
    assert db.normalize_stored_times(conn) == (1, 0)
    conn.close()
```

Under Q2 rejected, `""` is unparseable: change the first test's expectation to `(2, 2)` and assert `t2` keeps `""`.

- [x] **Step 2: Run and confirm failure.** Expected: `AttributeError` for `normalize_stored_times`.

- [x] **Step 3: Implement** in `src/fleetcom/db.py` (add `from . import util`):

```python
# Literals, not caller input: these names are interpolated into SQL.
_TIME_COLUMNS = {"tasks": ("due", "remind_at"), "events": ("start", "end")}
_UTC_GLOB = (
    "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z"
)


def normalize_stored_times(conn: sqlite3.Connection) -> tuple[int, int]:
    """Rewrite stored times in UTC; return (rows fixed, values left as they were).

    Old servers can still write offset times until they restart, so this runs
    at every startup. It reads first, so a clean database costs no write.
    """
    plans = []
    left = 0
    for table, columns in _TIME_COLUMNS.items():
        dirty = " OR ".join(f"({c} IS NOT NULL AND {c} NOT GLOB ?)" for c in columns)
        rows = conn.execute(
            f"SELECT id, {', '.join(columns)} FROM {table} WHERE {dirty}",
            [_UTC_GLOB] * len(columns),
        ).fetchall()
        for row in rows:
            new = {}
            for column in columns:
                try:
                    new[column] = util.to_utc(row[column])
                except ValueError:
                    left += 1
                    new[column] = row[column]
            if any(new[c] != row[c] for c in columns):
                plans.append((table, columns, row, new))
    fixed = 0
    try:
        with conn:
            for table, columns, row, new in plans:
                sets = ", ".join(f"{c} = ?" for c in columns)
                guards = " AND ".join(f"{c} IS ?" for c in columns)
                try:
                    cur = conn.execute(
                        f"UPDATE {table} SET {sets} WHERE id = ? AND {guards}",
                        [
                            *(new[c] for c in columns),
                            row["id"],
                            *(row[c] for c in columns),
                        ],
                    )
                except sqlite3.IntegrityError:
                    left += 1
                    continue
                fixed += cur.rowcount
    except sqlite3.OperationalError as error:
        if "locked" not in str(error):
            raise
        return 0, 0
    return fixed, left
```

In `server.main`, after `db.migrate(conn)`:

```python
    fixed, left = db.normalize_stored_times(conn)
    if fixed or left:
        print(
            f"fleetcom-mcp: normalized times in {fixed} rows to UTC; left {left} values",
            file=sys.stderr,
        )
```

- [x] **Step 4: Run the full suite and linters.** Expected: all pass.
- [x] **Step 5: Commit** `src/fleetcom/db.py`, `src/fleetcom/server.py`, and `tests/test_db.py`.

### Task C5: Docs and merge

**Files:**
- Modify: `src/skills/fleetcom/SKILL.md`, `src/skills/fleetcom/references/tools.md`, `CHANGELOG.md`, `dev/SKELETON.md` (Timestamps invariant; Logic Flow first bullet), `dev/CODEMAP.md` (util, db rows), `docs/ISSUES.md`, the feature's docs.

- [x] **Step 1:** In `SKILL.md`, replace "Write `due` and `remind_at` as UTC... does not validate them." with: "Write times in ISO-8601. Fleetcom stores them in UTC, reads a time without an offset as UTC, and rejects anything it cannot parse. Pass `""` to clear `due`, `remind_at`, or `end`." Drop the last sentence if Q2 is not approved.
- [x] **Step 2:** Add a clearing example to `references/tools.md`: `task_update(task_id="...", due="")`.
- [x] **Step 3:** Rewrite the Timestamps invariant in `dev/SKELETON.md`: every stored time is in `now_iso()` format because entity writes normalize and startup repairs, except values the repair could not parse.
- [x] **Step 4:** Add to `CHANGELOG.md`: "Fix `due_now` and `agenda_today` misjudging times with a UTC offset: times are stored in UTC, and existing rows are repaired at startup." "Reject unparseable times." "Let `""` clear `due`, `remind_at`, and `end`."
- [x] **Step 5:** In `docs/ISSUES.md`, mark the offset bug and the `due=""` item resolved. Mark the duplicate Planned item ("`due`, `remind_at`, `start`, and `end` are unvalidated strings") resolved by the same branch.
- [x] **Step 6:** Dispatch a reviewer subagent ("Code review before a merge"). Ask it to check the events `CHECK` path and the repair's lock handling specifically. Record findings in `utc-timestamps-tests.md`.
- [x] **Step 7:** Commit the docs. Ask the user to approve the merge. After the merge, run the tests and linters on `main`.

---

## Branch D: `promote-hardening` (item 6, deploy docs from item 8)

### Design

**Problems** (`docs/ISSUES.md`, Planned):

1. `--skill-only` stamps `deploy/mcp.promoted-sha` although no install happened (`scripts/promote.sh:45`).
2. The guard checks only `src/`, does not require `main`, and runs no tests (`:18`).
3. `rm -rf` then `cp` (`:26-27`) leaves consumers with no skill if `cp` fails.
4. `uv tool install` ignores `uv.lock`, so transitive packages drift from the tested set (`:42`).
5. `fleetcom-mcp` has no `--version`, which `development/AGENTS.md` (Releases) requires.
6. The deploy flow is not documented in README, CODEMAP, or `AGENTS.md`.

**Change.**

- `--version` prints `fleetcom-mcp <version>` from `importlib.metadata.version("fleetcom")`, through argparse `action="version"`. It exits before the database is opened, so it needs no config and no privileges.
- `promote.sh`:
  - Refuse unless the whole tree is clean (`git status --porcelain` is empty) and the branch is `main`.
  - Refuse if `uv lock --check` fails. Otherwise `uv run` rewrites a stale `uv.lock` partway through the promote, and `uv export --frozen` exports the stale lock.
  - Run `uv run pytest -q`, `uv run ruff check`, and `uv run ruff format --check` first; stop on any failure.
  - Copy the skill to `$SKILL_DST.new`, then swap: move the old copy to `$SKILL_DST.old`, move the new copy into place, remove the old copy.
  - Install with lock constraints: `uv export --frozen --no-dev --no-emit-project --no-hashes -o "$tmp/constraints.txt"`, then `uv tool install --python 3.11 --from "$REPO_ROOT" fleetcom --force --reinstall --constraints "$tmp/constraints.txt"`. These flags exist in uv 0.13.6 (checked with `--help` on 2026-11-14). Task D3 Step 4 checks that the installed `mcp` version matches `uv.lock`.
  - After the install, require that `fleetcom-mcp --version` prints the version in `pyproject.toml`.
  - Stamp `mcp.promoted-sha` only after a successful install. Remove the `deploy/mcp/promoted-sha` fallback, because `deploy/` always exists after the `mkdir`.

**Rejected:** embedding the git SHA in the build. It needs a generated file inside the package, and whether `uv_build` includes an untracked file was not checked. The version plus `mcp.promoted-sha` identifies the build, as long as each promote that changes code bumps the version (Task E1).

**Testing.** There is no shell test harness, and adding one is out of scope. Task D3 checks the guards by running the script in states where it must refuse before changing anything. The full run is Task E2.

### Task D1: Design doc and test plan

**Files:**
- Create: `dev/features/promote-hardening.md`, `dev/features/promote-hardening-tests.md`

- [x] **Step 1:** Run `git switch -c promote-hardening` from an up-to-date `main` that includes Branch B.
- [x] **Step 2:** Run the tests and linters and record the baseline.
- [x] **Step 3:** Load `maintaining-dev-docs`. Write the design doc from the Design section above.
- [x] **Step 4:** Write the test plan with the checks from Tasks D2 and D3.
- [x] **Step 5:** Review the test plan with the user. Do not continue until the user confirms it.
- [x] **Step 6:** Commit both docs on the branch.

### Task D2: `fleetcom-mcp --version`

**Files:**
- Modify: `src/fleetcom/server.py` (`_parse_args`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `_parse_args` from Task B3.

- [x] **Step 1: Write the failing test** in `tests/test_cli.py`:

```python
from importlib.metadata import version


def test_version_prints_the_package_version_without_opening_a_database(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("FLEETCOM_DB_PATH", str(tmp_path / "missing.db"))
    with pytest.raises(SystemExit) as exit_info:
        _parse_args(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"fleetcom-mcp {version('fleetcom')}"
    assert not (tmp_path / "missing.db").exists()
```

- [x] **Step 2: Run and confirm failure.** Expected: argparse exits with code 2 for an unknown argument.
- [x] **Step 3: Implement.** Add `from importlib.metadata import version` to `server.py`, and in `_parse_args` before `parse_args`:

```python
    parser.add_argument(
        "--version", action="version", version=f"fleetcom-mcp {version('fleetcom')}"
    )
```

- [x] **Step 4: Run the full suite and linters.** Expected: all pass.
- [x] **Step 5: Commit** `src/fleetcom/server.py` and `tests/test_cli.py`.

### Task D3: Harden `scripts/promote.sh`

**Files:**
- Modify: `scripts/promote.sh`

- [x] **Step 1: Rewrite the script:**

```bash
#!/usr/bin/env bash
# promote.sh: Promote reviewed, committed source to deploy/ and install the MCP server.
#
# Run only on a clean main, after the changes being promoted passed review.
# Consumers symlink to deploy/skills/fleetcom/, so promotion is what makes
# content live for Hermes profiles and Claude Code sessions.
#
# Usage:
#   scripts/promote.sh              # promote skill + reinstall MCP server
#   scripts/promote.sh --skill-only # skill only; skips uv tool install

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy"
SKILL_SRC="$REPO_ROOT/src/skills/fleetcom"
SKILL_DST="$DEPLOY_DIR/skills/fleetcom"
SKILL_ONLY=false
[ "${1:-}" = "--skill-only" ] && SKILL_ONLY=true

cd "$REPO_ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: the working tree is not clean. Commit (after review) before promoting." >&2
  exit 1
fi
if [ "$(git branch --show-current)" != "main" ]; then
  echo "ERROR: promote only from main." >&2
  exit 1
fi
if ! uv lock --check; then
  echo "ERROR: uv.lock is out of date. Run uv lock and commit it." >&2
  exit 1
fi

uv run pytest -q
uv run ruff check
uv run ruff format --check

GIT_SHA="$(git rev-parse HEAD)"
mkdir -p "$DEPLOY_DIR/skills"

# Swap in the new skill so a failed copy never leaves consumers without one.
rm -rf "$SKILL_DST.new" "$SKILL_DST.old"
cp -R "$SKILL_SRC" "$SKILL_DST.new"
printf '%s\n' "$GIT_SHA" > "$SKILL_DST.new/.promoted-sha"
if [ -e "$SKILL_DST" ]; then mv "$SKILL_DST" "$SKILL_DST.old"; fi
mv "$SKILL_DST.new" "$SKILL_DST"
rm -rf "$SKILL_DST.old"

# Claude Code's auto-updater has been reported to delete symlinked directories
# under ~/.claude/skills/, so re-assert the link on every run.
mkdir -p "$HOME/.claude/skills"
ln -sfn "$SKILL_DST" "$HOME/.claude/skills/fleetcom"

echo "promoted skill -> $SKILL_DST"
echo "symlinked -> $HOME/.claude/skills/fleetcom"

if [ "$SKILL_ONLY" = false ]; then
  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT
  # uv tool install ignores uv.lock; constraints keep the tested versions.
  uv export --frozen --no-dev --no-emit-project --no-hashes -o "$TMP_DIR/constraints.txt" >/dev/null
  uv tool install --python 3.11 --from "$REPO_ROOT" fleetcom \
    --force --reinstall --constraints "$TMP_DIR/constraints.txt" >/dev/null
  # Ask uv where it put the launcher; ~/.local/bin may not be on PATH here.
  LAUNCHER="$(uv tool dir --bin)/fleetcom-mcp"
  EXPECTED="fleetcom-mcp $(uv version --short)"
  INSTALLED="$("$LAUNCHER" --version)"
  if [ "$INSTALLED" != "$EXPECTED" ]; then
    echo "ERROR: installed '$INSTALLED', expected '$EXPECTED'." >&2
    exit 1
  fi
  printf '%s\n' "$GIT_SHA" > "$DEPLOY_DIR/mcp.promoted-sha"
  echo "reinstalled $INSTALLED -> $LAUNCHER"
fi

echo "promoted from git sha: $GIT_SHA"
```

- [x] **Step 2: Check the syntax.** Run `bash -n scripts/promote.sh`. If `shellcheck` is installed, run `shellcheck scripts/promote.sh` and fix its findings; do not add it to the project.
- [x] **Step 3: Check that `uv version --short` prints the project version and `uv tool dir --bin` prints the launcher folder** in uv 0.13.6. If it does not, read the version with `uv run python -c "from importlib.metadata import version; print(version('fleetcom'))"` instead, and record which form was used.
- [x] **Step 4: Check the guards without promoting.** On the branch, with the script uncommitted, run `scripts/promote.sh --skill-only`. Expected: "the working tree is not clean", and `deploy/` unchanged (`git status` shows only the script, and `stat deploy/mcp.promoted-sha` shows the same time). After committing, run it again on the branch. Expected: "promote only from main", and `deploy/` unchanged.
- [x] **Step 5:** Check the constraints in a scratch install: every package in the scratch tool environment matches `uv export --frozen` (`mcp` alone proves nothing, because `pyproject.toml` already bounds it).
- [x] **Step 6: Commit** `scripts/promote.sh`.

### Task D4: Docs and merge

**Files:**
- Modify: `README.md` (a Deploy section), `dev/CODEMAP.md` (a `scripts/promote.sh` row), `AGENTS.md` (one rule), `CHANGELOG.md`, `docs/ISSUES.md`, the feature's docs.

- [x] **Step 1:** Add a README Deploy section: promote from a clean `main` with `scripts/promote.sh`; what it checks; that it writes `deploy/` and installs `fleetcom-mcp`; that clients must restart to load the new build; `fleetcom-mcp --version` reports the installed build.
- [x] **Step 2:** Add a CODEMAP row: "`scripts/promote.sh` | checks a clean `main` and runs the tests, swaps the skill into `deploy/`, installs `fleetcom-mcp` with `uv.lock` constraints, and stamps the promoted SHA".
- [x] **Step 3:** Add to `AGENTS.md`, under a new `## Deploy` heading: "Never hand-edit `deploy/`. Only `scripts/promote.sh` writes it." Ask the user to approve this `AGENTS.md` change in the merge request.
- [x] **Step 4:** Add to `CHANGELOG.md`: "Add `fleetcom-mcp --version`." "Fix `scripts/promote.sh`: require a clean `main`, run the tests and linters, swap the skill in place, install with `uv.lock` constraints, and stamp `mcp.promoted-sha` only after an install."
- [x] **Step 5:** Mark resolved in `docs/ISSUES.md`: the three `promote.sh` items and the deploy-docs item.
- [x] **Step 6:** Dispatch a reviewer subagent ("Code review before a merge"). Record findings in `promote-hardening-tests.md`.
- [x] **Step 7:** Commit the docs. Ask the user to approve the merge. After the merge, run the tests and linters on `main`.

---

## E: Promote, restart, and live checks (item 5; Codex and Hermes follow-ups from item 8)

Promote installs outside the project folder, so `development/AGENTS.md` (Releases) treats it as a release. Only the user authorizes it.

### Task E1: Version bump and release prep

**Files:**
- Modify: `pyproject.toml` (version), `CHANGELOG.md`

- [x] **Step 1:** Load the `releasing-dev-projects` skill and follow its gate.
- [x] **Step 2:** Propose bumping `version` from `0.1.0` to `0.2.0`, and moving the four branches' CHANGELOG lines under a `0.2.0` heading. After the bump, run `uv lock` so the lock's `fleetcom` entry matches, and run `uv lock --check` to confirm. Wait for the user's approval of the commit on `main`, which includes `pyproject.toml`, `uv.lock`, and `CHANGELOG.md`.
- [x] **Step 3:** Ask the user or hermes-manager to confirm that every client config (`~/.hermes/config.yaml` and the four Hermes profiles, `~/.claude.json`, `~/.codex/config.toml`) passes `--db` with the absolute path of the existing live database. Branch B makes a wrong path a startup error.
- [ ] **Step 4:** Ask the user whether to tag, push, or make a GitHub release; the skill holds those steps.

### Task E2: Promote

- [x] **Step 1:** With the user's authorization, run `scripts/promote.sh` on a clean `main`.
- [x] **Step 2:** Run `fleetcom-mcp --version`. Expected: `fleetcom-mcp 0.2.0`. Confirm that `deploy/mcp.promoted-sha` equals `git rev-parse HEAD`.
- [x] **Step 3:** Ask the user to restart the Hermes gateway and every Claude Code and Codex session, because running servers keep the old code until they restart.

### Task E3: Live checks

Run each check through the installed `fleetcom-mcp`, against the live database, with the user's go-ahead. Delete every test row afterwards and confirm the delete.

- [x] **Step 1 (A):** Call `task_update` with a made-up id. Expected: an error that names the id.
- [x] **Step 2 (B):** Run `fleetcom-mcp --db <scratch folder>/does-not-exist.db`. Expected: exit status 1 and the `--create-db` message, and no file created.
- [/] **Step 3 (C):** After the restart, re-run the read-only count from Task C1 Step 3. Expected: no row with a parseable non-UTC time. Check the Hermes gateway log or a session's MCP log for the `normalized times in N rows` line. Create a task with `due` in `-08:00`, read it back in UTC, then delete it.
- [/] **Step 4 (item 5):** Run the list-truncation checks that are still open (`dev/features/list-truncation-tests.md`, Results, "Not checked yet"): `agenda_today` through a Hermes client, and one `task_list` each from Hermes, Claude Code, and Codex. Use an interactive Codex session, because `codex exec` refuses the tool call under approval policy `never`.
Progress on 2026-11-15, not yet recorded in the `-tests.md` files:

- E2: promoted `3b693f3` on 2026-11-14. The installed launcher prints `fleetcom-mcp 0.2.0`, and both promoted-SHA stamps equal `3b693f3`. The user confirmed on 2026-11-15 that every client was restarted.
- Step 1: `task_update` with id `e3-check-nonexistent-id` returned `tasks: no row with id 'e3-check-nonexistent-id'`.
- Step 2: the installed binary on a missing scratch database exited 1 with the `--create-db` message and created no file. On a zero-byte file, it exited 1 with "not a fleetcom database" and left the file at 0 bytes.
- Step 3: the read-only count found 0 non-UTC values in 65 tasks and 0 events. A due of `2026-11-20T09:00:00-08:00` was stored as `2026-11-20T17:00:00Z`, and the test task was deleted. Open: the log check for the `normalized times` line, because the logs sit outside the project folder and the user has not yet allowed reading them.
- Step 4: Claude Code `task_list(limit=5)` returned 5 rows with `truncated: true`, and `agenda_today` returned 29 due tasks with both flags false. A `hermes -z` one-shot on the default profile gave the same results. Open: Codex. `codex exec --help` hangs inside the Claude Code sandbox; the user has not answered whether to retry outside the sandbox.

- [ ] **Step 5:** Record the results under `## Results` in each feature's `-tests.md`, and in `list-truncation-tests.md`.
- [ ] **Step 6:** Mark resolved in `docs/ISSUES.md`: the restart and client-check step, and the two Codex confirmation steps if Step 4 covered them.

### Task E4: Hermes follow-ups

- [ ] **Step 1:** Send hermes-manager one message (`peer-projects` skill) with three items: the CoS job should raise `limit` when `truncated` is true on the review queue query (`docs/ISSUES.md`, Next steps); unknown ids now return an error; a missing database is now a startup error unless `--create-db` is passed.
- [ ] **Step 2:** In the same message, ask about retiring `reconcile-fleet-dbs.sh` (`docs/ISSUES.md`, Next steps). That work is hermes-manager's.
- [ ] **Step 3:** Mark the CoS-update step resolved in `docs/ISSUES.md` once hermes-manager confirms.

## Plan review

A `Plan` subagent (Fable, high effort) reviewed this plan on 2026-11-14 against `61777b0`, using scratch databases and the project venv (Python 3.11.15, SQLite 3.53.1, mcp 2.2.0, uv 0.13.6). The user limited the review to findings with a clear execution path.

| ID | Finding | Evidence | Resolution |
|----|---------|----------|------------|
| F1 | The version bump leaves `uv.lock` stale; `uv run` in `promote.sh` then rewrites it partway through | `uv lock --check` exits 1 after the bump on an archive copy | E1 runs `uv lock`; `promote.sh` refuses a stale lock |
| F2 | `astimezone` raises `OverflowError` for `0001-01-01T00:00:00+05:00`, which escapes `to_utc` and would stop startup through the repair | Reproduced on Python 3.11.15 | `to_utc` maps it to `ValueError`; test case added |
| F3 | The untracked plan file makes the new `promote.sh` guard refuse | `git status` shows `?? docs/superpowers/` | Q7 is settled before Branch A |
| F4 | `--db` naming a folder raises `OperationalError` from `connect`, so startup prints a traceback | `mode=rw` on a folder raises `OperationalError` | `main` catches it; test added |
| F5 | `event_list` with `""` bounds returns an empty list with no error | `events.py:34-36` | Not changed: current code returns the same empty list for `""` bounds |
| F6 | One new A2 test passes on current code | `crud.py:55-56` | Step 2 says it passes before and after |

## Deferred

These stay open in `docs/ISSUES.md`, and no branch here changes them:

- Content edits on a reviewed task keep `reviewed=1` (Q5).
- How Codex gets the skill (`docs/ISSUES.md`, Planned). Task E3 checks only that Codex can call the tools.

import json

import pytest
from mcp import Client

from fleetcom import agenda, contacts, db, events, tasks, util
from fleetcom.server import build_server

OLD = "2026-01-01T00:00:00Z"
NEW = "2026-06-01T00:00:00Z"
PAST = "2020-01-01T00:00:00Z"
LIST_CALLS = {
    "task_list": ("tasks", {}),
    "event_list": (
        "events",
        {"start": "2026-01-01T00:00:00Z", "end": "2026-12-31T00:00:00Z"},
    ),
    "contact_search": ("contacts", {"query": "name"}),
}


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(str(tmp_path / "fleetcom.db"))
    db.migrate(conn)
    return conn


@pytest.fixture
def server(conn):
    return build_server(conn)


def add_task(conn, summary="task", created_at=OLD, **columns):
    task_id = tasks.create(conn, created_by="test", summary=summary)
    columns["created_at"] = created_at
    assignments = ", ".join(f"{name} = ?" for name in columns)
    with conn:
        conn.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ?",
            [*columns.values(), task_id],
        )
    return task_id


def add_finished(conn, count, created_at=NEW, **columns):
    for i in range(count):
        add_task(
            conn,
            f"finished {i}",
            created_at,
            status="completed",
            reviewed=1,
            **columns,
        )


def add_rows(conn, tool, count):
    for i in range(count):
        if tool == "task_list":
            add_task(conn, f"task {i}")
        elif tool == "event_list":
            events.create(
                conn,
                created_by="test",
                summary=f"event {i}",
                start="2026-06-01T09:00:00Z",
                end="2026-06-01T10:00:00Z",
            )
        else:
            contacts.create(conn, created_by="test", name=f"name {i:03}")


def add_due(conn, count):
    for i in range(count):
        add_task(conn, f"due {i}", due=f"2020-01-01T00:{i:02}:00Z")


def add_events_today(conn, count):
    today = util.now_iso()[:10]
    for i in range(count):
        events.create(
            conn,
            created_by="test",
            summary=f"event {i}",
            start=f"{today}T12:00:00Z",
            end=f"{today}T13:00:00Z",
        )


async def call(server, tool, **args):
    async with Client(server) as client:
        res = await client.call_tool(tool, args)
    assert res.is_error is False
    return res.structured_content


async def test_unfiltered_list_shows_the_newest_task_and_flags_the_cut(conn, server):
    add_task(conn, created_at=OLD)
    for i in range(49):
        add_task(conn, f"middle {i}", "2026-02-01T00:00:00Z")
    newest = add_task(conn, "newest", NEW)

    result = await call(server, "task_list")

    assert result["tasks"][0]["id"] == newest
    assert len(result["tasks"]) == 50
    assert result["truncated"] is True


async def test_last_task_created_in_one_second_comes_first(conn, server):
    for i in range(50):
        add_task(conn, f"task {i}")
    last = add_task(conn, "last")

    result = await call(server, "task_list")

    assert result["tasks"][0]["id"] == last


@pytest.mark.parametrize("tool", LIST_CALLS)
@pytest.mark.parametrize(("count", "truncated"), [(50, False), (51, True)])
async def test_flag_boundary(conn, server, tool, count, truncated):
    key, args = LIST_CALLS[tool]
    add_rows(conn, tool, count)

    result = await call(server, tool, **args)

    assert result["truncated"] is truncated
    assert len(result[key]) == 50


@pytest.mark.parametrize(("count", "truncated"), [(50, False), (51, True)])
async def test_flag_boundary_for_due_now(conn, server, count, truncated):
    add_due(conn, count)

    result = await call(server, "task_list", due_now=True)

    assert result["truncated"] is truncated
    assert len(result["tasks"]) == 50


async def test_larger_limit_returns_every_row_unflagged(conn, server):
    add_rows(conn, "task_list", 51)

    result = await call(server, "task_list", limit=51)

    assert len(result["tasks"]) == 51
    assert result["truncated"] is False


@pytest.mark.parametrize(
    "columns",
    [
        {"status": "open"},
        {"status": "in-progress"},
        {"status": "blocked", "blocked_reason": "vendor"},
    ],
    ids=lambda columns: columns["status"],
)
async def test_old_live_work_survives_newer_finished_tasks(conn, server, columns):
    live = add_task(conn, "live", OLD, **columns)
    add_finished(conn, 60)

    result = await call(server, "task_list")

    assert live in [row["id"] for row in result["tasks"]]


async def test_old_unreviewed_task_survives_newer_accepted_tasks(conn, server):
    unreviewed = add_task(conn, "unreviewed", OLD, status="completed")
    add_finished(conn, 60)

    result = await call(server, "task_list")

    assert unreviewed in [row["id"] for row in result["tasks"]]


async def test_review_queue_query_puts_the_unreviewed_task_first(conn, server):
    unreviewed = add_task(conn, "unreviewed", OLD, status="completed")
    add_finished(conn, 60)

    result = await call(server, "task_list", status="completed")

    assert result["tasks"][0]["id"] == unreviewed


async def test_order_is_active_then_unreviewed_then_reviewed(conn, server):
    open_ = add_task(conn, "open", "2026-01-01T00:00:00Z")
    progress = add_task(conn, "progress", "2026-01-02T00:00:00Z", status="in-progress")
    blocked = add_task(
        conn,
        "blocked",
        "2026-01-03T00:00:00Z",
        status="blocked",
        blocked_reason="vendor",
    )
    unreviewed = add_task(
        conn, "unreviewed", "2026-02-01T00:00:00Z", status="completed"
    )
    reviewed = add_task(
        conn, "reviewed", "2026-03-01T00:00:00Z", status="completed", reviewed=1
    )

    result = await call(server, "task_list")

    assert [row["id"] for row in result["tasks"]] == [
        blocked,
        progress,
        open_,
        unreviewed,
        reviewed,
    ]


async def test_each_finished_tier_is_newest_first(conn, server):
    older = add_task(conn, "older", OLD, status="completed")
    newer = add_task(conn, "newer", NEW, status="completed")
    older_done = add_task(conn, "older done", OLD, status="completed", reviewed=1)
    newer_done = add_task(conn, "newer done", NEW, status="completed", reviewed=1)

    result = await call(server, "task_list")

    assert [row["id"] for row in result["tasks"]] == [
        newer,
        older,
        newer_done,
        older_done,
    ]


async def test_reviewed_flag_does_not_lower_an_active_task(conn, server):
    older = add_task(conn, "older", OLD, reviewed=1)
    newer = add_task(conn, "newer", NEW)
    done = add_task(conn, "done", "2026-07-01T00:00:00Z", status="completed")

    result = await call(server, "task_list")

    assert [row["id"] for row in result["tasks"]] == [newer, older, done]


async def test_more_live_tasks_than_the_limit_stay_flagged(conn, server):
    add_rows(conn, "task_list", 61)

    result = await call(server, "task_list")

    assert len(result["tasks"]) == 50
    assert result["truncated"] is True


async def test_owner_list_keeps_old_open_work(conn, server):
    live = add_task(conn, "live", OLD, owner="agent")
    add_finished(conn, 50, owner="agent")
    add_task(conn, "other", NEW, owner="someone-else")

    result = await call(server, "task_list", owner="agent")

    assert live in [row["id"] for row in result["tasks"]]
    assert {row["owner"] for row in result["tasks"]} == {"agent"}


async def test_due_now_keeps_oldest_due_first(conn, server):
    add_due(conn, 55)

    result = await call(server, "task_list", due_now=True)

    assert [row["summary"] for row in result["tasks"][:2]] == ["due 0", "due 1"]
    assert result["truncated"] is True


@pytest.mark.parametrize(
    ("due", "today", "tasks_cut", "events_cut"),
    [(51, 50, True, False), (50, 51, False, True)],
)
def test_each_agenda_flag_follows_its_own_list(conn, due, today, tasks_cut, events_cut):
    add_due(conn, due)
    add_events_today(conn, today)

    result = agenda.today(conn)

    assert result["tasks_truncated"] is tasks_cut
    assert result["events_truncated"] is events_cut
    assert len(result["tasks_due"]) == 50
    assert len(result["events_today"]) == 50


async def test_named_agenda_widening_calls_return_every_row(conn, server):
    add_due(conn, 51)
    add_events_today(conn, 51)
    today = util.now_iso()[:10]

    due = await call(server, "task_list", due_now=True, limit=51)
    today_events = await call(
        server,
        "event_list",
        start=f"{today}T00:00:00Z",
        end=f"{today}T23:59:59Z",
        limit=51,
    )

    assert len(due["tasks"]) == 51
    assert len(today_events["events"]) == 51


@pytest.mark.parametrize("tool", LIST_CALLS)
async def test_flag_is_the_first_key_in_the_text_block(conn, server, tool):
    _, args = LIST_CALLS[tool]
    add_rows(conn, tool, 1)

    async with Client(server) as client:
        res = await client.call_tool(tool, args)

    assert next(iter(json.loads(res.content[0].text))) == "truncated"


async def test_agenda_flags_come_first_in_the_text_block(server):
    async with Client(server) as client:
        res = await client.call_tool("agenda_today", {})

    assert list(json.loads(res.content[0].text))[:2] == [
        "tasks_truncated",
        "events_truncated",
    ]


@pytest.mark.parametrize("tool", LIST_CALLS)
@pytest.mark.parametrize("limit", [0, -1, "too large"])
async def test_invalid_limit_is_an_error_that_names_limit(server, tool, limit):
    _, args = LIST_CALLS[tool]
    if limit == "too large":
        limit = util.MAX_LIMIT + 1

    async with Client(server) as client:
        res = await client.call_tool(tool, {**args, "limit": limit})

    assert res.is_error is True
    assert "limit" in res.content[0].text


@pytest.mark.parametrize("tool", LIST_CALLS)
async def test_limit_edges_succeed(conn, server, tool):
    key, args = LIST_CALLS[tool]
    add_rows(conn, tool, 2)

    one = await call(server, tool, **args, limit=1)
    most = await call(server, tool, **args, limit=util.MAX_LIMIT)

    assert len(one[key]) == 1
    assert one["truncated"] is True
    assert len(most[key]) == 2
    assert most["truncated"] is False


@pytest.mark.parametrize("tool", [*LIST_CALLS, "agenda_today"])
async def test_tool_description_tells_agents_about_truncation(server, tool):
    async with Client(server) as client:
        listed = await client.list_tools()

    description = next(t.description for t in listed.tools if t.name == tool)

    assert "truncated" in description

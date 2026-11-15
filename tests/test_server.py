import asyncio
import sqlite3

import pytest
from mcp import Client

from fleetcom import db, tasks
from fleetcom.server import build_server


@pytest.fixture
def server(tmp_path):
    conn = db.connect(str(tmp_path / "fleetcom.db"), create=True)
    db.migrate(conn)
    return build_server(conn)


async def test_tools_list_has_all_fifteen(server):
    # HERMES_TASK.md's own count (13) omits task_accept/task_reject despite listing
    # them as tools; 6 task + 4 event + 4 contact + agenda_today = 15. See report.
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools.tools}
    assert names == {
        "task_create",
        "task_list",
        "task_update",
        "task_delete",
        "task_accept",
        "task_reject",
        "event_create",
        "event_list",
        "event_update",
        "event_delete",
        "contact_create",
        "contact_search",
        "contact_update",
        "contact_delete",
        "agenda_today",
    }


async def test_task_lifecycle(server):
    async with Client(server) as client:
        res = await client.call_tool(
            "task_create", {"summary": "write tests", "created_by": "agent-1"}
        )
        assert res.is_error is False
        task_id = res.structured_content["id"]

        res = await client.call_tool("task_list", {"status": "open"})
        assert [t["id"] for t in res.structured_content["tasks"]] == [task_id]

        res = await client.call_tool(
            "task_update", {"task_id": task_id, "status": "completed"}
        )
        assert res.structured_content["ok"] is True

        res = await client.call_tool("task_list", {"status": "completed"})
        assert len(res.structured_content["tasks"]) == 1

        res = await client.call_tool("task_delete", {"task_id": task_id})
        assert res.structured_content["ok"] is True


async def test_task_update_cannot_touch_created_by(server):
    """created_by isn't a task_update parameter, so it can never be reassigned via the tool
    surface -- passing it is simply not a recognized field, not a validation bypass."""
    async with Client(server) as client:
        res = await client.call_tool("task_create", {"summary": "x", "created_by": "a"})
        task_id = res.structured_content["id"]

        res = await client.call_tool(
            "task_update", {"task_id": task_id, "created_by": "hacker"}
        )
        assert res.is_error is False
        assert (
            res.structured_content["ok"] is False
        )  # no recognized field was given, so nothing changed

        res = await client.call_tool("task_list", {})
        assert res.structured_content["tasks"][0]["created_by"] == "a"


async def test_task_update_invalid_status_returns_meaningful_error(server):
    """A CHECK-constraint rejection must reach the caller as a specific, actionable
    message, not the generic 'Error executing tool X' every crash produces."""
    async with Client(server) as client:
        res = await client.call_tool("task_create", {"summary": "x", "created_by": "a"})
        task_id = res.structured_content["id"]

        res = await client.call_tool(
            "task_update", {"task_id": task_id, "status": "bogus"}
        )
    assert res.is_error is True
    message = res.content[0].text
    assert message != "Error executing tool task_update"
    assert "status" in message


async def test_event_create_invalid_range_returns_meaningful_error(server):
    async with Client(server) as client:
        res = await client.call_tool(
            "event_create",
            {
                "summary": "e",
                "start": "2026-01-02T00:00:00Z",
                "end": "2026-01-01T00:00:00Z",
                "created_by": "a",
            },
        )
    assert res.is_error is True
    message = res.content[0].text
    assert message != "Error executing tool event_create"
    assert "start" in message


async def test_task_list_due_now(server):
    async with Client(server) as client:
        res = await client.call_tool(
            "task_create",
            {
                "summary": "renew lease",
                "remind_at": "2020-01-01T00:00:00Z",
                "created_by": "a",
            },
        )
        due_id = res.structured_content["id"]
        await client.call_tool(
            "task_create",
            {
                "summary": "future",
                "remind_at": "2099-01-01T00:00:00Z",
                "created_by": "a",
            },
        )

        res = await client.call_tool("task_list", {"due_now": True})
    assert [t["id"] for t in res.structured_content["tasks"]] == [due_id]


async def test_task_accept_and_reject(server):
    async with Client(server) as client:
        res = await client.call_tool("task_create", {"summary": "x", "created_by": "a"})
        task_id = res.structured_content["id"]

        res = await client.call_tool(
            "task_accept", {"task_id": task_id, "actor": "cos"}
        )
        assert res.structured_content["ok"] is False  # not completed yet

        await client.call_tool(
            "task_update",
            {"task_id": task_id, "status": "completed", "result_summary": "done"},
        )
        res = await client.call_tool(
            "task_accept", {"task_id": task_id, "actor": "cos-agent"}
        )
        assert res.structured_content["ok"] is True

        res = await client.call_tool(
            "task_reject",
            {"task_id": task_id, "actor": "cos-agent", "note": "redo this"},
        )
        assert res.structured_content["ok"] is True

        res = await client.call_tool("task_list", {"status": "in-progress"})
        tasks_ = res.structured_content["tasks"]
        assert len(tasks_) == 1
        assert tasks_[0]["reviewed"] == 0
        assert "redo this" in tasks_[0]["description"]
        assert "cos-agent" in tasks_[0]["description"]


@pytest.mark.parametrize(
    "tool, args",
    [
        ("task_update", {"task_id": "missing-1", "status": "open"}),
        ("task_delete", {"task_id": "missing-1"}),
        ("task_accept", {"task_id": "missing-1", "actor": "cos"}),
        ("task_reject", {"task_id": "missing-1", "actor": "cos", "note": "n"}),
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


async def test_task_update_blocked_without_reason_returns_meaningful_error(server):
    async with Client(server) as client:
        res = await client.call_tool("task_create", {"summary": "x", "created_by": "a"})
        task_id = res.structured_content["id"]

        res = await client.call_tool(
            "task_update", {"task_id": task_id, "status": "blocked"}
        )
    assert res.is_error is True
    message = res.content[0].text
    assert message != "Error executing tool task_update"
    assert "blocked_reason" in message


async def test_agenda_today(server):
    async with Client(server) as client:
        res = await client.call_tool(
            "task_create",
            {
                "summary": "renew now",
                "remind_at": "2020-01-01T00:00:00Z",
                "created_by": "a",
            },
        )
        due_id = res.structured_content["id"]

        res = await client.call_tool("agenda_today", {})
    assert [t["id"] for t in res.structured_content["tasks_due"]] == [due_id]
    assert res.structured_content["events_today"] == []


async def test_event_create_and_list(server):
    async with Client(server) as client:
        await client.call_tool(
            "event_create",
            {
                "summary": "standup",
                "start": "2026-09-15T09:00:00Z",
                "created_by": "a",
            },
        )
        res = await client.call_tool(
            "event_list",
            {"start": "2026-09-01T00:00:00Z", "end": "2026-09-30T00:00:00Z"},
        )
    assert [e["summary"] for e in res.structured_content["events"]] == ["standup"]


async def test_contact_create_and_search(server):
    async with Client(server) as client:
        await client.call_tool(
            "contact_create",
            {"name": "Acme Plumbing", "created_by": "a", "kind": "vendor"},
        )
        res = await client.call_tool("contact_search", {"query": "acme"})
    assert [c["name"] for c in res.structured_content["contacts"]] == ["Acme Plumbing"]


async def test_concurrent_rejected_writes_do_not_lose_reported_writes(tmp_path):
    conn = db.connect(str(tmp_path / "fleetcom.db"), create=True)
    db.migrate(conn)
    server = build_server(conn)
    target = tasks.create(conn, created_by="a", summary="target")

    async with Client(server) as client:
        calls = []
        for i in range(150):
            calls.append(
                client.call_tool(
                    "task_create", {"summary": f"keep {i}", "created_by": "a"}
                )
            )
            calls.append(
                client.call_tool(
                    "task_update", {"task_id": target, "status": "blocked"}
                )
            )
        results = await asyncio.wait_for(
            asyncio.gather(*calls, return_exceptions=True), timeout=30
        )

    reported = [
        r.structured_content["id"]
        for r in results
        if getattr(r, "structured_content", None) and "id" in r.structured_content
    ]
    assert len(reported) == 150
    assert [i for i in reported if tasks.get(conn, i) is None] == []
    conn.close()


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


async def test_empty_string_clears_a_time_through_the_tools(tmp_path):
    conn = db.connect(str(tmp_path / "fleetcom.db"), create=True)
    db.migrate(conn)
    async with Client(build_server(conn)) as client:
        task = await asyncio.wait_for(
            client.call_tool(
                "task_create",
                {"summary": "x", "created_by": "a", "due": "2026-11-02T09:00:00Z"},
            ),
            timeout=10,
        )
        task_id = task.structured_content["id"]
        event = await asyncio.wait_for(
            client.call_tool(
                "event_create",
                {
                    "summary": "x",
                    "created_by": "a",
                    "start": "2026-11-02T09:00:00Z",
                    "end": "2026-11-02T10:00:00Z",
                },
            ),
            timeout=10,
        )
        event_id = event.structured_content["id"]
        cleared_task = await asyncio.wait_for(
            client.call_tool("task_update", {"task_id": task_id, "due": ""}),
            timeout=10,
        )
        cleared_event = await asyncio.wait_for(
            client.call_tool("event_update", {"event_id": event_id, "end": ""}),
            timeout=10,
        )
    assert cleared_task.is_error is False
    assert cleared_task.structured_content["ok"] is True
    assert cleared_event.is_error is False
    assert cleared_event.structured_content["ok"] is True
    assert tasks.get(conn, task_id)["due"] is None
    assert (
        conn.execute("SELECT end FROM events WHERE id = ?", (event_id,)).fetchone()[0]
        is None
    )


async def test_event_update_description_says_how_to_clear_end(server):
    async with Client(server) as client:
        tools = await asyncio.wait_for(client.list_tools(), timeout=10)
    description = next(t.description for t in tools.tools if t.name == "event_update")
    assert "end=''" in description
    assert "start cannot be cleared" in description

import pytest
from mcp import Client

from fleetcom import db
from fleetcom.server import build_server


@pytest.fixture
def server(tmp_path):
    conn = db.connect(str(tmp_path / "fleetcom.db"))
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

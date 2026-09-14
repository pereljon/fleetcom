from fleetcom import agenda, events, tasks, util


def test_today_combines_due_tasks_and_todays_events(conn):
    due_task = tasks.create(
        conn, created_by="a", summary="renew now", remind_at="2020-01-01T00:00:00Z"
    )
    tasks.create(
        conn, created_by="a", summary="future", remind_at="2099-01-01T00:00:00Z"
    )

    today_date = util.now_iso()[:10]
    todays_event = events.create(
        conn, created_by="a", summary="standup", start=f"{today_date}T12:00:00Z"
    )
    events.create(
        conn, created_by="a", summary="next month", start="2099-01-01T00:00:00Z"
    )

    result = agenda.today(conn)

    assert [t["id"] for t in result["tasks_due"]] == [due_task]
    assert [e["id"] for e in result["events_today"]] == [todays_event]

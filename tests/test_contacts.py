from fleetcom import contacts


def test_create_and_get(conn):
    cid = contacts.create(
        conn,
        created_by="a",
        name="Acme Plumbing",
        kind="vendor",
        phone="555-1234",
        tags="plumbing,emergency",
    )
    got = contacts.get(conn, cid)
    assert got["name"] == "Acme Plumbing"
    assert got["kind"] == "vendor"


def test_search_matches_name_or_tags(conn):
    plumber = contacts.create(
        conn, created_by="a", name="Acme Plumbing", tags="plumbing,emergency"
    )
    contacts.create(conn, created_by="a", name="Beta Electric", tags="electric")

    by_name = contacts.search(conn, query="acme")
    assert [c["id"] for c in by_name] == [plumber]

    by_tag = contacts.search(conn, query="plumbing")
    assert [c["id"] for c in by_tag] == [plumber]


def test_update_and_delete(conn):
    cid = contacts.create(conn, created_by="a", name="x")
    assert contacts.update(conn, cid, phone="555-0000") is True
    assert contacts.get(conn, cid)["phone"] == "555-0000"
    assert contacts.delete(conn, cid) is True
    assert contacts.get(conn, cid) is None

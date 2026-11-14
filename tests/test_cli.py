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


def test_main_exits_with_a_message_for_a_file_that_is_not_a_database(
    monkeypatch, tmp_path
):
    path = tmp_path / "notes.txt"
    path.write_text("not a database")
    monkeypatch.setattr("sys.argv", ["fleetcom-mcp", "--db", str(path)])
    with pytest.raises(SystemExit) as exit_info:
        server.main()
    assert "cannot open database" in str(exit_info.value.code)
    assert path.read_text() == "not a database"


def test_main_exits_with_a_message_for_an_empty_file(monkeypatch, tmp_path):
    path = tmp_path / "fleetcom.db"
    path.touch()
    monkeypatch.setattr("sys.argv", ["fleetcom-mcp", "--db", str(path)])
    with pytest.raises(SystemExit) as exit_info:
        server.main()
    message = str(exit_info.value.code)
    assert "cannot open database" in message
    assert "not a fleetcom database" in message
    assert path.stat().st_size == 0

from fleetcom.server import _resolve_db_path


def test_resolve_db_path_flag_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FLEETCOM_DB_PATH", str(tmp_path / "env.db"))
    flag_path = str(tmp_path / "flag.db")
    assert _resolve_db_path(["--db", flag_path]) == flag_path


def test_resolve_db_path_falls_back_to_env_when_no_flag(monkeypatch, tmp_path):
    env_path = str(tmp_path / "env.db")
    monkeypatch.setenv("FLEETCOM_DB_PATH", env_path)
    assert _resolve_db_path([]) == env_path

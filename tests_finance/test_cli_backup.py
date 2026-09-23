"""Comandos backup, snapshots y restore (CF1-21)."""

import sqlite3

from cuentafaro.cli import main


class _FakeSettings:
    def __init__(self, database_url: str):
        self.database_url = database_url


def _create_sqlite_db(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO demo (value) VALUES ('original')")
        connection.commit()


def test_backup_creates_private_snapshot(tmp_path, monkeypatch) -> None:
    import re

    database = tmp_path / "live" / "cuentafaro.db"
    _create_sqlite_db(database)
    fn_context = _FakeSettings(f"sqlite:///{database}")
    monkeypatch.setattr("cuentafaro.cli.get_settings", lambda: fn_context)

    backups = tmp_path / "backups"
    assert main(["backup", "--path", str(backups)]) == 0
    snapshots = list(backups.glob("cuentafaro-*.db"))
    assert len(snapshots) == 1
    assert re.fullmatch(r"cuentafaro-\d{8}T\d{6}Z\.db", snapshots[0].name)


def test_snapshots_lists_created_snapshot(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "live" / "cuentafaro.db"
    _create_sqlite_db(database)
    fn_context = _FakeSettings(f"sqlite:///{database}")
    monkeypatch.setattr("cuentafaro.cli.get_settings", lambda: fn_context)

    backups = tmp_path / "backups"
    assert main(["backup", "--path", str(backups)]) == 0
    assert main(["snapshots", "--path", str(backups)]) == 0
    output = capsys.readouterr().out
    assert "cuentafaro-" in output
    assert "bytes" in output


def test_restore_recovers_database(tmp_path, monkeypatch) -> None:
    live_database = tmp_path / "live" / "cuentafaro.db"
    _create_sqlite_db(live_database)
    first_settings = _FakeSettings(f"sqlite:///{live_database}")
    monkeypatch.setattr("cuentafaro.cli.get_settings", lambda: first_settings)

    backups = tmp_path / "backups"
    assert main(["backup", "--path", str(backups)]) == 0
    snapshot = next(backups.glob("cuentafaro-*.db"))

    restored_database = tmp_path / "restored" / "cuentafaro.db"
    second_settings = _FakeSettings(f"sqlite:///{restored_database}")
    monkeypatch.setattr("cuentafaro.cli.get_settings", lambda: second_settings)

    assert main(["restore", "--path", str(snapshot)]) == 0
    assert restored_database.exists()
    with sqlite3.connect(restored_database) as connection:
        (value,) = connection.execute("SELECT value FROM demo WHERE id = 1").fetchone()
        assert value == "original"


def test_restore_rejects_invalid_snapshot_name(tmp_path, monkeypatch, capsys) -> None:
    other = tmp_path / "file.txt"
    other.write_text("no es un snapshot")
    whatever_settings = _FakeSettings(f"sqlite:///{tmp_path / 'x.db'}")
    monkeypatch.setattr("cuentafaro.cli.get_settings", lambda: whatever_settings)
    assert main(["restore", "--path", str(other)]) == 1
    assert "no parece un snapshot" in capsys.readouterr().out

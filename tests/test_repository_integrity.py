from pathlib import Path


def test_dependency_lockfile_is_valid_utf8_text() -> None:
    content = Path("uv.lock").read_text(encoding="utf-8")
    assert content.startswith("version = 1\n")
    assert 'name = "jonathan-ai-pm"' in content

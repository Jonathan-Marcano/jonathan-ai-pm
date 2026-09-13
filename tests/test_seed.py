from pathlib import Path

from jonathan_ai_pm.seed import load_snapshot
from jonathan_ai_pm.services import DomainStore


def test_demo_snapshot_loads(session) -> None:
    load_snapshot(session, Path("data/seed/demo-workspace.json"))
    store = DomainStore(session)
    assert len(store.list("workspace")) == 1
    assert len(store.list("action_item")) == 1
    assert store.get("action_item", "act_demo_confirm_dependencies").task_id == (
        "tsk_demo_validate_dependencies"
    )

from datetime import UTC, datetime, timedelta

from faroflow.integrations.contracts import (
    READ_ONLY_CAPABILITIES,
    ExternalDocumentMetadata,
)
from faroflow.integrations.google_drive import GoogleDriveAdapter, GoogleDriveConfig
from faroflow.integrations.reconciliation import reconcile_drive_files
from faroflow.models import Deliverable, ExternalIdentity, SyncRun, SyncRunError
from faroflow.services import DomainStore

START = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)


def build_project(session) -> None:
    store = DomainStore(session)
    store.create("workspace", id="wrk_demo", name="Demo", timezone="America/Santiago")
    store.create("client", id="cli_demo", workspace_id="wrk_demo", name="Demo client")
    store.create("project", id="prj_demo", client_id="cli_demo", name="Demo project")
    store.create(
        "deliverable",
        id="dlv_demo",
        project_id="prj_demo",
        title="Project plan",
        due_at=datetime(2026, 9, 30, tzinfo=UTC).date(),
    )


def driving_link(session, *, external_id="file-1", name="Project plan.pdf"):
    return DomainStore(session).link_drive_file(
        "dlv_demo",
        source_system="google-drive",
        external_id=external_id,
        name=name,
        web_url=f"https://drive.example.test/{external_id}",
        mime_type="application/pdf",
    )


def metadata(
    external_id: str = "file-1",
    *,
    name: str = "Project plan.pdf",
    version: str | int | None = 7,
    modified: datetime | None = START,
) -> ExternalDocumentMetadata:
    return ExternalDocumentMetadata(
        source_system="google-drive",
        external_id=external_id,
        name=name,
        web_url=f"https://drive.example.test/{external_id}",
        mime_type="application/pdf",
        etag=str(version) if version is not None else None,
        last_modified_at=modified,
    )


class FakedDriveAdapter:
    source_system = "google-drive"
    capabilities = READ_ONLY_CAPABILITIES

    def __init__(self, files=None, error: Exception | None = None):
        self._files = {item.external_id: item for item in (files or [])}
        self._error = error
        self.calls = 0

    def get_metadata(self, external_id: str) -> ExternalDocumentMetadata:
        self.calls += 1
        if self._error is not None:
            raise self._error
        if external_id not in self._files:
            raise RuntimeError(f"file not found: {external_id}")
        return self._files[external_id]


def refresh(session, adapter, **kwargs) -> SyncRun:
    return reconcile_drive_files(session, adapter=adapter, **kwargs)


def test_unlinked_files_are_not_refreshed(session) -> None:
    build_project(session)
    adapter = FakedDriveAdapter([metadata("file-1")])

    run = refresh(session, adapter)

    assert run.status == "succeeded"
    assert run.seen_count == 0
    assert run.unchanged_count == 0
    assert adapter.calls == 0
    assert session.query(SyncRun).count() == 1


def test_first_refresh_links_drive_metadata(session) -> None:
    build_project(session)
    driving_link(session, name="Old name.pdf")
    run = refresh(session, FakedDriveAdapter([metadata()]))

    assert run.status == "succeeded"
    assert run.seen_count == 1
    assert run.updated_count == 1
    assert run.unchanged_count == 0

    identity = session.query(ExternalIdentity).one()
    assert identity.entity_kind == "deliverable"
    assert identity.external_name == "Project plan.pdf"
    assert identity.external_version == "7"
    assert identity.mime_type == "application/pdf"
    assert identity.external_modified_at.replace(tzinfo=UTC) == START
    assert session.query(Deliverable).one().drive_url == "https://drive.example.test/file-1"


def test_repeated_refresh_is_idempotent(session) -> None:
    build_project(session)
    driving_link(session)
    adapter = FakedDriveAdapter([metadata()])

    first = refresh(session, adapter)
    second = refresh(session, adapter)

    assert first.updated_count == 1
    assert second.status == "succeeded"
    assert second.updated_count == 0
    assert second.unchanged_count == 1
    assert session.query(ExternalIdentity).count() == 1
    assert session.query(Deliverable).one().drive_url == "https://drive.example.test/file-1"


def test_refresh_keeps_manual_drive_url_in_sync(session) -> None:
    build_project(session)
    driving_link(session)
    deliverable = session.query(Deliverable).one()
    deliverable.drive_url = "https://example.test/manual"
    session.commit()

    run = refresh(session, FakedDriveAdapter([metadata()]))

    assert run.updated_count == 1
    assert session.query(Deliverable).one().drive_url == "https://drive.example.test/file-1"


def test_provider_metadata_change_updates_in_place(session) -> None:
    build_project(session)
    driving_link(session)
    changed = metadata(name="Project plan v2.pdf", version=8, modified=START + timedelta(hours=1))

    run = refresh(session, FakedDriveAdapter([changed]))

    assert run.updated_count == 1
    identity = session.query(ExternalIdentity).one()
    assert identity.external_name == "Project plan v2.pdf"
    assert identity.external_version == "8"
    assert identity.external_modified_at.replace(tzinfo=UTC) == START + timedelta(hours=1)


def test_unknown_external_id_is_skipped_with_error(session) -> None:
    build_project(session)
    driving_link(session, external_id="file-missing")

    run = refresh(session, FakedDriveAdapter([]))

    assert run.status == "partial"
    assert run.seen_count == 1
    assert run.skipped_count == 1
    assert run.error_count == 1
    assert session.query(SyncRunError).count() == 1
    assert session.query(ExternalIdentity).one().external_version is None


def test_requested_ids_filter_refresh_scope(session) -> None:
    build_project(session)
    driving_link(session, external_id="file-1")
    driving_link(session, external_id="file-2", name="Other.pdf")

    run = refresh(session, FakedDriveAdapter([metadata("file-1")]), external_ids=["file-1"])

    assert run.status == "succeeded"
    assert run.seen_count == 1
    assert run.updated_count == 1


def test_metadata_mismatch_is_rejected(session) -> None:
    build_project(session)
    driving_link(session, external_id="file-1")

    run = refresh(
        session,
        FakedDriveAdapter([metadata("file-other")]),
    )

    assert run.status == "partial"
    assert run.skipped_count == 1
    assert run.error_count == 1
    identity = session.query(ExternalIdentity).one()
    assert identity.external_id == "file-1"
    assert identity.external_name == "Project plan.pdf"


def test_failed_refresh_never_touches_existing_data(session) -> None:
    build_project(session)
    driving_link(session)
    session.query(ExternalIdentity).one()

    run = refresh(session, FakedDriveAdapter([metadata()], error=RuntimeError("boom")))

    assert run.status == "partial"
    assert run.seen_count == 1
    assert run.skipped_count == 1
    assert run.error_count == 1
    assert session.query(ExternalIdentity).count() == 1
    delivered = session.query(Deliverable).one()
    assert delivered.drive_url == "https://drive.example.test/file-1"


def test_adapter_is_read_only_and_body_is_never_fetched(session) -> None:
    assert GoogleDriveAdapter(lambda: "token", config=GoogleDriveConfig()).capabilities == (
        READ_ONLY_CAPABILITIES
    )
    assert GoogleDriveAdapter(lambda: "token").source_system == "google-drive"


def test_token_policy_for_missing_credentials(session) -> None:
    build_project(session)
    driving_link(session)

    def no_token():
        raise RuntimeError("no tenant token")

    adapter = GoogleDriveAdapter(no_token)
    run = refresh(session, adapter)

    assert run.status == "partial"
    assert run.skipped_count == 1
    assert run.error_count == 1
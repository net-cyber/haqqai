"""Upload one legal volume with a split profile and index one document per decision."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from onyx.connectors.models import InputType
from onyx.db.document import get_documents_for_cc_pair
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.enums import AccessType
from onyx.server.documents.models import DocumentSource, FileUploadResponse
from tests.integration.common_utils.managers.cc_pair import CCPairManager
from tests.integration.common_utils.managers.connector import ConnectorManager
from tests.integration.common_utils.managers.credential import CredentialManager
from tests.integration.common_utils.managers.document import DocumentManager
from tests.integration.common_utils.managers.file import FileManager
from tests.integration.common_utils.test_models import DATestCCPair, DATestUser
from tests.integration.common_utils.vespa import vespa_fixture

VOLUME = Path(__file__).parent / "test_files" / "cassation_small.md"
CASE_NUMBERS = ["94952", "96364", "152719", "99954"]
EDIT_MARKER = "HAQQAI_EDIT_MARKER_7f3a"


def _document_ids(cc_pair: DATestCCPair) -> set[str]:
    with get_session_with_current_tenant() as db_session:
        return {doc.id for doc in get_documents_for_cc_pair(db_session, cc_pair.id)}


def test_split_volume_is_indexed_per_decision_and_editable(
    reset: None,  # noqa: ARG001
    admin_user: DATestUser,
    vespa_client: vespa_fixture,
) -> None:
    content = VOLUME.read_bytes()

    preview = FileManager.preview_connector_file_split(
        [("volume.md", content)], admin_user, split_profile="auto"
    )
    assert preview.status_code == 200, preview.text
    source = preview.json()["sources"][0]
    assert (source["profile"], source["unit_count"]) == ("cassation", 4)

    response = FileManager.upload_connector_files(
        [("volume.md", content)],
        admin_user,
        content_type="text/markdown",
        split_profile="cassation",
    )
    assert response.status_code == 200, response.text
    upload = FileUploadResponse(**response.json())
    assert upload.file_names == [f"volume__case-{n}.md" for n in CASE_NUMBERS]
    assert upload.split_summary is not None
    assert upload.split_summary[0].unit_count == 4

    before = datetime.now(timezone.utc)
    credential = CredentialManager.create(
        source=DocumentSource.FILE,
        credential_json={},
        user_performing_action=admin_user,
    )
    connector = ConnectorManager.create(
        name=f"LegalSplit-{uuid.uuid4().hex[:8]}",
        source=DocumentSource.FILE,
        input_type=InputType.LOAD_STATE,
        connector_specific_config={
            "file_locations": upload.file_paths,
            "file_names": upload.file_names,
            "zip_metadata_file_id": None,
        },
        access_type=AccessType.PUBLIC,
        groups=[],
        user_performing_action=admin_user,
    )
    cc_pair = CCPairManager.create(
        credential_id=credential.id,
        connector_id=connector.id,
        access_type=AccessType.PUBLIC,
        user_performing_action=admin_user,
    )
    CCPairManager.run_once(
        cc_pair, from_beginning=True, user_performing_action=admin_user
    )
    CCPairManager.wait_for_indexing_completion(
        cc_pair=cc_pair, after=before, user_performing_action=admin_user
    )

    # One document per decision, titled by its case number.
    expected_ids = {f"FILE_CONNECTOR__{file_id}" for file_id in upload.file_paths}
    with get_session_with_current_tenant() as db_session:
        documents = get_documents_for_cc_pair(db_session, cc_pair.id)
    assert {doc.id for doc in documents} == expected_ids
    assert sorted(doc.semantic_id.split(" ")[2] for doc in documents) == sorted(
        CASE_NUMBERS
    )

    # The file list shows where each file came from.
    listing = FileManager.list_connector_files(connector.id, admin_user)
    assert listing.status_code == 200, listing.text
    files = listing.json()["files"]
    assert {f["parent_file_name"] for f in files} == {"volume.md"}
    assert all(f["editable"] for f in files)

    # Edit one decision in place: same file id, same document id.
    edited_id = upload.file_paths[1]
    current = FileManager.get_connector_file_content(
        connector.id, edited_id, admin_user
    )
    assert current.status_code == 200, current.text
    assert "ONYX_METADATA" not in current.json()["content"]
    assert current.json()["metadata"]["case_number"] == "96364"

    edited_at = datetime.now(timezone.utc)
    saved = FileManager.update_connector_file_content(
        connector.id,
        edited_id,
        current.json()["content"] + f"\n\n{EDIT_MARKER}\n",
        admin_user,
    )
    assert saved.status_code == 200, saved.text
    CCPairManager.wait_for_indexing_completion(
        cc_pair=cc_pair, after=edited_at, user_performing_action=admin_user
    )
    assert _document_ids(cc_pair) == expected_ids
    with get_session_with_current_tenant() as db_session:
        chunks = DocumentManager.fetch_documents_for_cc_pair(
            cc_pair.id, db_session, vespa_client
        )
    edited_doc_id = f"FILE_CONNECTOR__{edited_id}"
    assert any(
        chunk.id == edited_doc_id and EDIT_MARKER in chunk.content for chunk in chunks
    )

    # A file id that is not on this connector cannot be read or written.
    foreign = FileManager.update_connector_file_content(
        connector.id, str(uuid.uuid4()), "text", admin_user
    )
    assert foreign.status_code == 404

    # Removing one decision prunes its document.
    pruned_after = datetime.now(timezone.utc)
    removed = FileManager.update_connector_files(
        connector.id, admin_user, file_ids_to_remove=[upload.file_paths[0]]
    )
    assert removed.status_code == 200, removed.text
    CCPairManager.wait_for_prune(
        cc_pair=cc_pair, after=pruned_after, user_performing_action=admin_user
    )
    assert _document_ids(cc_pair) == expected_ids - {
        f"FILE_CONNECTOR__{upload.file_paths[0]}"
    }

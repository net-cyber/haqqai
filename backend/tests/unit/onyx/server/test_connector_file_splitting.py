import io
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response, UploadFile
from starlette.datastructures import Headers

from onyx.configs.constants import DocumentSource, FileOrigin
from onyx.error_handling.exceptions import OnyxError
from onyx.file_processing.legal.ethiopian_legal_splitter import SplitProfile
from onyx.server.documents import connector as connector_module
from onyx.server.documents.connector import (
    get_connector_file_content,
    preview_file_split,
    update_connector_file_content,
    upload_files,
)
from onyx.server.documents.file_splitting import parse_split_profile
from onyx.server.documents.models import ConnectorFileContentUpdateRequest

FIXTURES = Path(__file__).parents[1] / "file_processing" / "legal" / "fixtures"
_MOD = "onyx.server.documents.connector"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _upload(content: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class _MemoryFileStore:
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = dict(files or {})
        self.saved: list[dict[str, Any]] = []

    def save_file(self, **kwargs: Any) -> str:
        file_id = kwargs.get("file_id") or f"id-{len(self.saved)}"
        self.files[file_id] = kwargs["content"].read()
        self.saved.append({**kwargs, "file_id": file_id})
        return file_id

    def read_file(self, file_id: str, mode: str | None = None) -> io.BytesIO:  # noqa: ARG002
        return io.BytesIO(self.files[file_id])


@pytest.fixture
def store() -> Iterator[_MemoryFileStore]:
    memory_store = _MemoryFileStore()
    with patch(f"{_MOD}.get_default_file_store", return_value=memory_store):
        yield memory_store


def test_upload_splits_legal_file(store: _MemoryFileStore) -> None:
    result = upload_files(
        [_upload(_fixture("family_small.md"), "family.md", "text/markdown")],
        FileOrigin.CONNECTOR_FILE_UPLOAD,
        split_profile=SplitProfile.AUTO,
    )

    assert len(result.file_paths) == 14
    assert result.file_names[0] == "family__front-matter.md"
    assert result.file_names[7] == "family__art-7.md"
    assert result.split_summary is not None
    summary = result.split_summary[0]
    assert (summary.source_name, summary.profile, summary.unit_count) == (
        "family.md",
        "proclamation",
        14,
    )

    saved = store.saved[7]
    assert saved["file_type"] == "text/markdown"
    assert saved["file_origin"] == FileOrigin.CONNECTOR_FILE_UPLOAD
    assert saved["file_metadata"]["split_parent_name"] == "family.md"
    assert saved["file_metadata"]["unit_id"] == "art-7"
    assert store.files[result.file_paths[7]].startswith(b"<!-- ONYX_METADATA=")


def test_upload_keeps_unsplittable_and_unmatched_files_whole(
    store: _MemoryFileStore,
) -> None:
    result = upload_files(
        [
            _upload(_fixture("amendment_proc_1070.md"), "amend.md", "text/markdown"),
            _upload(b"%PDF-1.4", "notes.pdf", "application/pdf"),
        ],
        FileOrigin.CONNECTOR,
        split_profile=SplitProfile.AUTO,
    )

    assert result.file_names == ["amend.md", "notes.pdf"]
    assert store.files[result.file_paths[0]] == _fixture("amendment_proc_1070.md")
    # Only splittable files get a summary.
    assert result.split_summary is not None
    assert [(s.source_name, s.profile, s.unit_count) for s in result.split_summary] == [
        ("amend.md", "none", 0)
    ]


def test_upload_without_profile_is_unchanged(
    store: _MemoryFileStore,  # noqa: ARG001
) -> None:
    result = upload_files(
        [_upload(_fixture("family_small.md"), "family.md", "text/markdown")],
        FileOrigin.CONNECTOR,
    )
    assert result.file_names == ["family.md"]
    assert result.split_summary is None


def test_upload_splits_files_inside_zip(
    store: _MemoryFileStore,  # noqa: ARG001
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("volume/cassation.md", _fixture("cassation_small.md"))
        zf.writestr("volume/readme.txt", "hello")

    with patch(f"{_MOD}.save_zip_metadata_to_file_store", return_value=None):
        result = upload_files(
            [_upload(buffer.getvalue(), "volume.zip", "application/zip")],
            FileOrigin.CONNECTOR,
            split_profile=SplitProfile.CASSATION,
        )

    assert result.file_names == [
        "cassation__case-94952.md",
        "cassation__case-96364.md",
        "cassation__case-152719.md",
        "cassation__case-99954.md",
        "readme.txt",
    ]


def test_preview_does_not_store(store: _MemoryFileStore) -> None:
    response = preview_file_split(
        [
            _upload(_fixture("cassation_small.md"), "vol.md", "text/markdown"),
            _upload(b"%PDF-1.4", "notes.pdf", "application/pdf"),
        ],
        split_profile="auto",
        _=MagicMock(),
    )

    assert store.saved == []
    assert not response.text_budget_exceeded
    cassation, pdf = response.sources
    assert (cassation.profile, cassation.unit_count, cassation.article_count) == (
        "cassation",
        4,
        4,
    )
    assert cassation.requested_profile == "auto"
    assert cassation.size_bytes == len(_fixture("cassation_small.md"))
    first = cassation.units[0]
    assert first.unit_id == "case-94952"
    assert first.file_name == "vol__case-94952.md"
    assert first.label == "ሰበር መ/ቁ 94952"
    assert first.text.startswith("የሰበር መዘገብ ቁጥር 94952")
    assert not first.text_truncated
    assert not pdf.splittable
    assert pdf.kept_whole is not None
    assert pdf.kept_whole.reason == "unsupported_type"


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(OnyxError):
        parse_split_profile("bogus")


# --- File content routes ---------------------------------------------------

_HEADER = {"title": "T", "doc_updated_at": "2026-01-01T00:00:00+00:00", "article": "7"}
_STORED = f"<!-- ONYX_METADATA={json.dumps(_HEADER)} -->\n\nአንቀጽ ፯ ዕድሜ\n\nold text\n"


@pytest.fixture
def content_env() -> Iterator[tuple[_MemoryFileStore, MagicMock]]:
    memory_store = _MemoryFileStore({"file-1": _STORED.encode()})
    record = SimpleNamespace(
        display_name="family__art-7.md",
        file_origin=FileOrigin.CONNECTOR_FILE_UPLOAD,
        file_type="text/markdown",
        file_metadata={"split_parent_name": "family.md", "unit_id": "art-7"},
    )
    connector = SimpleNamespace(
        source=DocumentSource.FILE,
        connector_specific_config={"file_locations": ["file-1"]},
    )
    trigger = MagicMock()
    with (
        patch(f"{_MOD}.fetch_connector_by_id", return_value=connector),
        patch(
            f"{_MOD}._fetch_and_check_file_connector_cc_pair_permissions",
            return_value=SimpleNamespace(id=42),
        ),
        patch(f"{_MOD}.get_filerecords_by_file_ids", return_value=[record]),
        patch(f"{_MOD}.get_default_file_store", return_value=memory_store),
        patch.object(connector_module, "_trigger_update_indexing", trigger),
    ):
        yield memory_store, trigger


def test_get_content_strips_header(
    content_env: tuple[_MemoryFileStore, MagicMock],  # noqa: ARG001
) -> None:
    response = Response()
    result = get_connector_file_content(
        1, "file-1", response, user=MagicMock(), db_session=MagicMock()
    )
    assert result.content == "አንቀጽ ፯ ዕድሜ\n\nold text\n"
    assert result.metadata["article"] == "7"
    assert response.headers["Cache-Control"] == "no-store"


def test_update_content_keeps_header_and_reindexes(
    content_env: tuple[_MemoryFileStore, MagicMock],
) -> None:
    memory_store, trigger = content_env
    # A header pasted into the editor is ignored.
    pasted = _STORED.replace("old text", "new text")
    update_connector_file_content(
        1,
        "file-1",
        ConnectorFileContentUpdateRequest(content=pasted),
        user=MagicMock(),
        db_session=MagicMock(),
    )

    saved = memory_store.saved[-1]
    assert saved["file_id"] == "file-1"
    assert saved["display_name"] == "family__art-7.md"
    assert saved["file_metadata"]["unit_id"] == "art-7"
    assert "edited_at" in saved["file_metadata"]

    stored = memory_store.files["file-1"].decode()
    assert stored.count("ONYX_METADATA") == 1
    assert '"article": "7"' in stored
    assert '"doc_updated_at": "2026-01-01' not in stored
    assert stored.endswith("አንቀጽ ፯ ዕድሜ\n\nnew text\n")
    assert trigger.call_args.args[0] == 42


@pytest.mark.parametrize(
    "file_id, content",
    [("file-2", "text"), ("file-1", "  \n")],
    ids=["file-of-another-connector", "empty-content"],
)
def test_update_content_rejects_bad_requests(
    content_env: tuple[_MemoryFileStore, MagicMock],
    file_id: str,
    content: str,
) -> None:
    memory_store, trigger = content_env
    with pytest.raises(OnyxError):
        update_connector_file_content(
            1,
            file_id,
            ConnectorFileContentUpdateRequest(content=content),
            user=MagicMock(),
            db_session=MagicMock(),
        )
    assert memory_store.saved == []
    trigger.assert_not_called()

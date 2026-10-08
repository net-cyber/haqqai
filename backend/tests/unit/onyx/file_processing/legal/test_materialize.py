import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from onyx.connectors.cross_connector_utils.miscellaneous_utils import (
    process_onyx_metadata,
)
from onyx.connectors.file.connector import _process_file
from onyx.connectors.models import TextSection
from onyx.file_processing.extract_file_text import extract_text_and_images
from onyx.file_processing.legal.ethiopian_legal_splitter import (
    LegalUnit,
    LegalUnitType,
    SplitProfile,
    split_legal_text,
)
from onyx.file_processing.legal.materialize import (
    render_unit,
    render_with_header,
    strip_header,
    unit_file_name,
)

FIXTURES = Path(__file__).parent / "fixtures"
SPLIT_AT = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
_EXTRACT_MOD = "onyx.file_processing.extract_file_text"


def _first_article() -> LegalUnit:
    text = (FIXTURES / "family_small.md").read_text(encoding="utf-8")
    result = split_legal_text(text, SplitProfile.PROCLAMATION)
    return next(u for u in result.units if u.unit_id == "art-7")


def _render(unit: LegalUnit) -> bytes:
    return render_unit(
        unit,
        source_name="family.md",
        source_sha256="abc",
        profile=SplitProfile.PROCLAMATION,
        index=7,
        total=14,
        split_at=SPLIT_AT,
        extra_tags={"jurisdiction": "federal"},
    ).content


def test_rendered_unit_round_trips_through_file_extraction() -> None:
    unit = _first_article()
    content = _render(unit)

    result = extract_text_and_images(
        io.BytesIO(content), "family__art-7.md", content_type="text/markdown"
    )
    onyx_metadata, tags = process_onyx_metadata(result.metadata)

    assert onyx_metadata.title == unit.title
    assert onyx_metadata.file_display_name == unit.display_name
    assert onyx_metadata.doc_updated_at == SPLIT_AT
    assert tags["article"] == "7"
    assert tags["legal_unit_type"] == LegalUnitType.PROCLAMATION_ARTICLE.value
    assert tags["source_file"] == "family.md"
    assert tags["jurisdiction"] == "federal"
    assert "ONYX_METADATA" not in result.text_content
    assert result.text_content.strip() == unit.text.strip()


def test_header_survives_unstructured() -> None:
    content = _render(_first_article())
    with (
        patch(f"{_EXTRACT_MOD}.get_unstructured_api_key", return_value="key"),
        patch(f"{_EXTRACT_MOD}.unstructured_to_text") as unstructured,
    ):
        result = extract_text_and_images(io.BytesIO(content), "family__art-7.md")
    unstructured.assert_not_called()
    assert result.metadata["article"] == "7"


def test_file_connector_builds_one_document_per_unit() -> None:
    unit = _first_article()
    documents = _process_file(
        file_id="file-1",
        file_name="family__art-7.md",
        file=io.BytesIO(_render(unit)),
        metadata=None,
        pdf_pass=None,
        file_type="text/markdown",
        stage=MagicMock(),
    )
    assert len(documents) == 1
    document = documents[0]
    assert document.id == "FILE_CONNECTOR__file-1"
    assert document.semantic_identifier == unit.display_name
    assert document.title == unit.title
    assert document.doc_updated_at == SPLIT_AT
    assert document.metadata["article"] == "7"
    section = document.sections[0]
    assert isinstance(section, TextSection)
    assert section.text.startswith("አንቀጽ ፯ ዕድሜ")


def test_header_values_are_sanitized() -> None:
    unit = LegalUnit(
        unit_id="art-1",
        unit_type=LegalUnitType.PROCLAMATION_ARTICLE,
        title="Law {draft}\nline --> end",
        display_name="Art 1",
        text="body",
        metadata={"chapter": "x" * 400},
    )
    content = render_unit(
        unit,
        source_name="law.md",
        source_sha256="abc",
        profile=SplitProfile.PROCLAMATION,
        index=0,
        total=1,
        split_at=SPLIT_AT,
    ).content.decode("utf-8")

    metadata, body = strip_header(content)
    assert metadata["title"] == "Law (draft) line -> end"
    assert len("chapter") + len(metadata["chapter"]) <= 255
    assert body == "body\n"


def test_strip_and_render_header() -> None:
    assert strip_header("plain text\n") == ({}, "plain text\n")
    assert strip_header("<!-- ONYX_METADATA={not json} -->\nbody") == (
        {},
        "<!-- ONYX_METADATA={not json} -->\nbody",
    )
    text = render_with_header({"title": "T"}, "line 1\n\nline 2")
    assert text.startswith('<!-- ONYX_METADATA={"title": "T"} -->\n\n')
    metadata, body = strip_header(text)
    assert metadata == {"title": "T"}
    assert render_with_header(metadata, body) == text
    assert render_with_header({}, "body") == "body\n"


def test_unit_file_name() -> None:
    assert unit_file_name("cassation 15 - 28.md", "case-1") == (
        "cassation 15 - 28__case-1.md"
    )
    assert unit_file_name("dir/a:b.docx", "art-2") == "a_b__art-2.md"
    assert unit_file_name("noext", "art-3") == "noext__art-3.md"

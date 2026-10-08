"""Split uploaded legal files into one stored markdown file per article or decision.

Used by the File connector upload routes. The split itself is pure text
processing (`onyx.file_processing.legal`); this module reads the upload, stores
each unit through the file store, and builds the summaries the UI shows.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from onyx.configs.constants import FileOrigin
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_processing.extract_file_text import (
    detect_encoding,
    get_file_ext,
    read_docx_file,
    read_text_file,
)
from onyx.file_processing.legal.ethiopian_legal_splitter import (
    LegalUnitType,
    SplitProfile,
    SplitResult,
    split_legal_text,
)
from onyx.file_processing.legal.materialize import (
    DISPLAY_NAME_KEY,
    TITLE_KEY,
    UPDATED_AT_KEY,
    render_unit,
)
from onyx.file_store.file_store import FileStore
from onyx.server.documents.models import (
    SplitPreviewSource,
    SplitPreviewUnit,
    SplitSummary,
)
from onyx.utils.logger import setup_logger

logger = setup_logger()

SPLITTABLE_EXTENSIONS = {".md", ".mdx", ".txt", ".docx"}
# Text files an admin can open and edit in the connector UI.
EDITABLE_EXTENSIONS = {".md", ".mdx", ".txt"}

_MAX_WARNINGS = 50
_MAX_PREVIEW_UNITS = 50

# Source-header keys that are not passed on to the units as tags.
_RESERVED_SOURCE_KEYS = {
    "id",
    "document_id",
    "link",
    "connector_type",
    "primary_owners",
    "secondary_owners",
    "file_display_name",
    "doc_updated_at",
    "time_updated",
    "filename",
    "mime_type",
    TITLE_KEY,
    DISPLAY_NAME_KEY,
    UPDATED_AT_KEY,
    "law_name",
    "volume",
}


def parse_split_profile(value: str | None) -> SplitProfile:
    try:
        return SplitProfile.parse(value)
    except ValueError as e:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(e)) from e


def is_splittable(file_name: str) -> bool:
    return get_file_ext(file_name) in SPLITTABLE_EXTENSIONS


def is_editable(file_name: str) -> bool:
    return get_file_ext(file_name) in EDITABLE_EXTENSIONS


def extract_split_source_text(
    file_name: str, data: bytes
) -> tuple[str, dict[str, Any]]:
    """Return (text, first-line ONYX_METADATA of the source)."""
    if get_file_ext(file_name) == ".docx":
        text, _ = read_docx_file(BytesIO(data), file_name, extract_images=False)
        return text, {}
    buffer = BytesIO(data)
    encoding = detect_encoding(buffer)
    text, metadata = read_text_file(
        buffer, encoding=encoding, ignore_onyx_metadata=False
    )
    return text, metadata


@dataclass
class PlannedSplit:
    source_name: str
    source_sha256: str
    result: SplitResult
    extra_tags: dict[str, str] = field(default_factory=dict)


def plan_split(file_name: str, data: bytes, profile: SplitProfile) -> PlannedSplit:
    """Run the splitter on one upload without storing anything.

    A first-line ONYX_METADATA header on the source can set `law_name` (or
    `title`) and `volume`; its other keys are copied to every unit as tags.
    """
    text, source_metadata = extract_split_source_text(file_name, data)
    law_name = source_metadata.get("law_name") or source_metadata.get(TITLE_KEY)
    volume = source_metadata.get("volume")
    result = split_legal_text(
        text,
        profile,
        source_name=file_name,
        law_name=str(law_name) if law_name else None,
        volume=str(volume) if volume else None,
    )
    extra_tags = {
        str(k): str(v)
        for k, v in source_metadata.items()
        if k not in _RESERVED_SOURCE_KEYS and isinstance(v, (str, int, float))
    }
    return PlannedSplit(
        source_name=file_name,
        source_sha256=hashlib.sha256(data).hexdigest(),
        result=result,
        extra_tags=extra_tags,
    )


def _capped_warnings(warnings: list[str]) -> list[str]:
    if len(warnings) <= _MAX_WARNINGS:
        return warnings
    hidden = len(warnings) - _MAX_WARNINGS
    return [*warnings[:_MAX_WARNINGS], f"… and {hidden} more"]


def build_split_summary(planned: PlannedSplit) -> SplitSummary:
    return SplitSummary(
        source_name=planned.source_name,
        profile=planned.result.profile.value,
        unit_count=len(planned.result.units),
        warnings=_capped_warnings(planned.result.warnings),
    )


def build_split_preview(planned: PlannedSplit) -> SplitPreviewSource:
    units = planned.result.units
    return SplitPreviewSource(
        source_name=planned.source_name,
        splittable=True,
        profile=planned.result.profile.value,
        unit_count=len(units),
        article_count=sum(
            1 for u in units if u.unit_type != LegalUnitType.FRONT_MATTER
        ),
        units=[
            SplitPreviewUnit(
                unit_id=unit.unit_id,
                display_name=unit.display_name,
                unit_type=unit.unit_type.value,
                chars=len(unit.text),
            )
            for unit in units[:_MAX_PREVIEW_UNITS]
        ],
        warnings=_capped_warnings(planned.result.warnings),
    )


def unsplittable_preview(file_name: str) -> SplitPreviewSource:
    return SplitPreviewSource(
        source_name=file_name,
        splittable=False,
        profile=SplitProfile.NONE.value,
        unit_count=0,
        article_count=0,
        units=[],
        warnings=[],
    )


def store_split_units(
    file_store: FileStore,
    planned: PlannedSplit,
    file_origin: FileOrigin,
) -> tuple[list[str], list[str]]:
    """Save every unit as its own markdown file. Returns (file ids, file names)."""
    split_at = datetime.now(timezone.utc)
    units = planned.result.units
    file_ids: list[str] = []
    file_names: list[str] = []
    for index, unit in enumerate(units):
        materialized = render_unit(
            unit,
            source_name=planned.source_name,
            source_sha256=planned.source_sha256,
            profile=planned.result.profile,
            index=index,
            total=len(units),
            split_at=split_at,
            extra_tags=planned.extra_tags,
        )
        file_id = file_store.save_file(
            content=BytesIO(materialized.content),
            display_name=materialized.file_name,
            file_origin=file_origin,
            file_type=materialized.file_type,
            file_metadata=materialized.file_metadata,
        )
        file_ids.append(file_id)
        file_names.append(materialized.file_name)
    logger.info(
        "Split %s into %d files with profile %s",
        planned.source_name,
        len(units),
        planned.result.profile.value,
    )
    return file_ids, file_names

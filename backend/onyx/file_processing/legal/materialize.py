"""Render split legal units as markdown files with an ONYX_METADATA header.

The File connector reads the header on line 1 (`_extract_onyx_metadata` in
`extract_file_text.py`): `title`, `file_display_name` and `doc_updated_at` set the
document fields and every other key becomes a document tag. The header parser only
accepts flat JSON on one line, so values never contain braces, newlines or `-->`.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from onyx.file_processing.legal.ethiopian_legal_splitter import LegalUnit, SplitProfile

UNIT_FILE_TYPE = "text/markdown"

# Keys the File connector maps to document fields instead of tags.
TITLE_KEY = "title"
DISPLAY_NAME_KEY = "file_display_name"
UPDATED_AT_KEY = "doc_updated_at"

# Tags with len(key) + len(value) > 255 are dropped (`check_tag_validity`).
_MAX_VALUE_CHARS = 200
_MAX_TITLE_CHARS = 500

_HEADER_LINE_RE = re.compile(r"^\s*<!--\s*ONYX_METADATA=(\{.*\})\s*-->\s*$")
_UNSAFE_VALUE_RE = re.compile(r"[\r\n\t]+")
_FILE_STEM_SAFE_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]+")


@dataclass(frozen=True)
class MaterializedUnit:
    file_name: str
    content: bytes
    file_type: str
    # Stored on the FileRecord. Drives grouping and provenance in the connector UI.
    file_metadata: dict[str, Any]


def _safe_value(value: str, max_chars: int = _MAX_VALUE_CHARS) -> str:
    value = _UNSAFE_VALUE_RE.sub(" ", value)
    value = value.replace("{", "(").replace("}", ")").replace("-->", "->")
    value = value.strip()
    return value if len(value) <= max_chars else value[: max_chars - 1] + "…"


def render_header(metadata: dict[str, str]) -> str:
    safe = {
        key: _safe_value(
            str(value),
            _MAX_TITLE_CHARS
            if key in (TITLE_KEY, DISPLAY_NAME_KEY)
            else _MAX_VALUE_CHARS,
        )
        for key, value in metadata.items()
        if str(value).strip()
    }
    return f"<!-- ONYX_METADATA={json.dumps(safe, ensure_ascii=False)} -->"


def strip_header(text: str) -> tuple[dict[str, str], str]:
    """Split a file into (header metadata, body). Metadata is empty without a header."""
    first_line, newline, rest = text.partition("\n")
    match = _HEADER_LINE_RE.match(first_line)
    if not match:
        return {}, text
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}, text
    if not isinstance(parsed, dict):
        return {}, text
    metadata = {str(k): str(v) for k, v in parsed.items()}
    return metadata, rest.lstrip("\n") if newline else ""


def render_with_header(metadata: dict[str, str], body: str) -> str:
    body = body.strip("\n")
    if not metadata:
        return body + "\n"
    return f"{render_header(metadata)}\n\n{body}\n"


def unit_file_name(source_name: str, unit_id: str) -> str:
    base = source_name.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    stem = _FILE_STEM_SAFE_RE.sub("_", stem).strip() or "source"
    return f"{stem}__{unit_id}.md"


def render_unit(
    unit: LegalUnit,
    *,
    source_name: str,
    source_sha256: str,
    profile: SplitProfile,
    index: int,
    total: int,
    split_at: datetime,
    extra_tags: dict[str, str] | None = None,
) -> MaterializedUnit:
    """Render one unit as a markdown file.

    `doc_updated_at` is fixed at split time so later index runs skip unchanged
    units by content hash instead of re-embedding every file.
    """
    header: dict[str, str] = {
        TITLE_KEY: unit.title,
        DISPLAY_NAME_KEY: unit.display_name,
        UPDATED_AT_KEY: split_at.isoformat(),
        **(extra_tags or {}),
        **unit.metadata,
        "source_file": source_name,
    }
    content = render_with_header(header, unit.text)
    return MaterializedUnit(
        file_name=unit_file_name(source_name, unit.unit_id),
        content=content.encode("utf-8"),
        file_type=UNIT_FILE_TYPE,
        file_metadata={
            "split_role": "unit",
            "split_parent_name": source_name,
            "split_parent_sha256": source_sha256,
            "split_profile": profile.value,
            "unit_id": unit.unit_id,
            "unit_index": index,
            "unit_count": total,
            "legal_unit_type": unit.unit_type.value,
            "unit_title": unit.display_name,
        },
    )

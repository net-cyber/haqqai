"""Build the split review: every unit with its text and the issues to check.

The review stores nothing. It runs the splitter on the upload and adds checks
that need the whole result: article numbers used twice, article numbers that
are missing from the file, and court decisions whose details could not be read.
"""

import difflib
import re
from collections import defaultdict

from onyx.file_processing.legal.ethiopian_legal_splitter import (
    KeptWhole,
    LegalUnit,
    LegalUnitType,
    SplitProfile,
    clean_line,
    int_to_geez_numeral,
)
from onyx.file_processing.legal.materialize import unit_file_name
from onyx.server.documents.file_splitting import PlannedSplit
from onyx.server.documents.models import (
    DuplicateNumberIssue,
    MissingFieldsIssue,
    NextMissingIssue,
    NumberRepairedIssue,
    OutOfSequenceIssue,
    SplitCaseField,
    SplitKeptWhole,
    SplitPathCrumb,
    SplitPathLevel,
    SplitPreviewIssue,
    SplitPreviewSource,
    SplitPreviewUnit,
    SplitProfileName,
    SplitUnitType,
)

# About 4 MB of UTF-8 Ethiopic text per response. Units past the budget get an excerpt.
PREVIEW_TEXT_BUDGET_CHARS = 1_500_000
PREVIEW_EXCERPT_CHARS = 2_000

# Matches _CASE_HEADER_FIELD_WINDOW in the splitter: decision details are read here.
CASE_HEADER_SEARCH_LINES = 15

_SOURCE_LINE_CHARS = 80
# Number gaps wider than this are treated as a misread number, not missing articles.
MAX_REPORTED_GAP = 20
# A suspect heading line is short and does not end like a sentence.
_SUSPECT_MAX_LINE_CHARS = 200
_SENTENCE_END_RE = re.compile(r"(?:።|፡፡|:|፡|;|፤)\s*$")
# Above this size the text comparison of duplicates uses the faster heuristic.
_EXACT_DIFF_MAX_CHARS = 20_000

_ARTICLE_TYPES = {LegalUnitType.PROCLAMATION_ARTICLE, LegalUnitType.CIVIL_CODE_ARTICLE}
_CASE_FIELDS: tuple[SplitCaseField, ...] = ("date", "applicant", "respondent")

_UNIT_TYPES: dict[LegalUnitType, SplitUnitType] = {
    LegalUnitType.PROCLAMATION_ARTICLE: "proclamation_article",
    LegalUnitType.CIVIL_CODE_ARTICLE: "civil_code_article",
    LegalUnitType.CASSATION_DECISION: "cassation_decision",
    LegalUnitType.FRONT_MATTER: "front_matter",
}
_PROFILE_NAMES: dict[SplitProfile, SplitProfileName] = {
    SplitProfile.AUTO: "auto",
    SplitProfile.PROCLAMATION: "proclamation",
    SplitProfile.CIVIL_CODE: "civil_code",
    SplitProfile.CASSATION: "cassation",
    SplitProfile.NONE: "none",
}
_PATH_LEVELS: dict[str, SplitPathLevel] = {
    "book": "book",
    "part": "part",
    "chapter": "chapter",
    "section": "section",
    "subsection": "subsection",
}


class TextBudget:
    """Shares one text budget across every source of a review request."""

    def __init__(self, total_chars: int = PREVIEW_TEXT_BUDGET_CHARS) -> None:
        self.remaining = total_chars
        self.exceeded = False

    def take(self, text: str) -> tuple[str, bool]:
        """Return (text to send, whether it is an excerpt)."""
        if len(text) <= self.remaining:
            self.remaining -= len(text)
            return text, False
        self.exceeded = True
        excerpt = text[:PREVIEW_EXCERPT_CHARS]
        self.remaining = max(0, self.remaining - len(excerpt))
        return excerpt, True


def _shorten(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def _lines(unit: LegalUnit) -> list[str]:
    return unit.text.split("\n")


def _header_range(unit: LegalUnit) -> range:
    """Raw line indices of the unit header within `unit.text`."""
    return range(unit.header_start, unit.header_start + max(1, unit.header_lines))


def _header_text(unit: LegalUnit) -> str:
    lines = _lines(unit)
    header = [clean_line(lines[i]) for i in _header_range(unit) if i < len(lines)]
    return _shorten(" ".join(line for line in header if line), _SOURCE_LINE_CHARS)


def _body(unit: LegalUnit) -> str:
    header = _header_range(unit)
    return "\n".join(
        line for index, line in enumerate(_lines(unit)) if index not in header
    ).strip()


def _differing_chars(a: str, b: str) -> int:
    """Characters that differ between two texts. 0 means the same text."""
    if a == b:
        return 0
    matcher = difflib.SequenceMatcher(
        None, a, b, autojunk=len(a) + len(b) > _EXACT_DIFF_MAX_CHARS
    )
    return sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    )


def _is_article(unit: LegalUnit) -> bool:
    return unit.unit_type in _ARTICLE_TYPES


def _duplicate_key(unit: LegalUnit) -> str | None:
    if _is_article(unit) and unit.number is not None:
        return f"article:{unit.number}"
    if unit.unit_type == LegalUnitType.CASSATION_DECISION:
        case_number = unit.metadata.get("case_number")
        return f"case:{case_number}" if case_number else None
    return None


def _duplicate_issues(units: list[LegalUnit]) -> dict[str, DuplicateNumberIssue]:
    groups: dict[str, list[LegalUnit]] = defaultdict(list)
    for unit in units:
        key = _duplicate_key(unit)
        if key is not None:
            groups[key].append(unit)

    issues: dict[str, DuplicateNumberIssue] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        # One comparison per pair, in document order, so both copies agree.
        distance: dict[tuple[str, str], int] = {}
        for unit in members:
            others = [other for other in members if other.unit_id != unit.unit_id]
            first, second = sorted([unit, others[0]], key=lambda u: members.index(u))
            pair = (first.unit_id, second.unit_id)
            if pair not in distance:
                distance[pair] = _differing_chars(_body(first), _body(second))
            issues[unit.unit_id] = DuplicateNumberIssue(
                other_unit_ids=[other.unit_id for other in others],
                differing_chars=distance[pair],
            )
    return issues


def _number_text(number: int, like: str) -> str:
    """Write `number` in the numeral system of `like`."""
    return str(number) if like.isascii() else int_to_geez_numeral(number)


def _suspect_line(
    unit: LegalUnit, missing_number: int
) -> tuple[int | None, str | None]:
    """A line inside `unit` that looks like the heading of a missing article.

    Only a line that starts with the article word (possibly missing letters, as
    in "ንቀጽ ፵፪") and the missing numeral counts; sub-article marks and
    cross-references do not.
    """
    if not unit.number_text or unit.number_text.isascii():
        return None, None
    numeral = re.escape(int_to_geez_numeral(missing_number))
    pattern = re.compile(rf"^\W*አ?ን?ቀ[ጽፅ]\s*{numeral}(?![፩-፼])")
    lines = _lines(unit)
    header_end = unit.header_start + max(1, unit.header_lines)
    for index in range(header_end, len(lines)):
        cleaned = clean_line(lines[index])
        if (
            cleaned
            and len(cleaned) <= _SUSPECT_MAX_LINE_CHARS
            and not _SENTENCE_END_RE.search(cleaned)
            and pattern.search(cleaned)
        ):
            return index, _shorten(cleaned, _SOURCE_LINE_CHARS)
    return None, None


def _sequence_issues(
    units: list[LegalUnit],
) -> tuple[dict[str, NextMissingIssue], set[str]]:
    """Missing article numbers, and units after an implausible jump.

    Returns (gap issue per unit after the gap, ids of units after a jump).
    Linear in the number of units, whatever the article numbers are.
    """
    numbered = [u for u in units if _is_article(u) and u.number is not None]
    present = {u.number for u in numbered}
    in_order = sorted(
        {u.number for u in numbered if u.number is not None and not u.out_of_sequence}
    )
    gaps: dict[str, NextMissingIssue] = {}
    jumps: set[str] = set()
    for previous, current in zip(in_order, in_order[1:], strict=False):
        if current - previous <= 1:
            continue
        if current - previous - 1 > MAX_REPORTED_GAP:
            jumps.update(u.unit_id for u in numbered if u.number == current)
            continue
        # Numbers that exist only as an out-of-order copy are not missing.
        missing = [n for n in range(previous + 1, current) if n not in present]
        if not missing:
            continue
        start = missing[0]
        end = start
        while end + 1 in missing:
            end += 1
        candidates = [u for u in numbered if u.number == start - 1]
        if not candidates:
            candidates = [u for u in numbered if u.number == previous]
        in_order_candidates = [u for u in candidates if not u.out_of_sequence]
        after = (in_order_candidates or candidates)[-1]
        suspect_line, suspect_text = _suspect_line(after, start)
        gaps[after.unit_id] = NextMissingIssue(
            from_number=start,
            to_number=end,
            from_text=_number_text(start, after.number_text),
            to_text=_number_text(end, after.number_text),
            suspect_line=suspect_line,
            suspect_text=suspect_text,
        )
    return gaps, jumps


def _header_search_lines(unit: LegalUnit) -> int:
    """Raw lines the splitter searched for decision details."""
    if unit.details_lines:
        return unit.details_lines
    seen = 0
    lines = _lines(unit)
    for index, line in enumerate(lines):
        if line.strip():
            seen += 1
            if seen > CASE_HEADER_SEARCH_LINES:
                return index + 1
    return len(lines)


def _issues_for(units: list[LegalUnit]) -> dict[str, list[SplitPreviewIssue]]:
    duplicates = _duplicate_issues(units)
    next_missing, jumps = _sequence_issues(units)
    issues: dict[str, list[SplitPreviewIssue]] = {}
    for unit in units:
        found: list[SplitPreviewIssue] = []
        if unit.repaired_from:
            found.append(
                NumberRepairedIssue(
                    source_number=unit.repaired_from, source_line=_header_text(unit)
                )
            )
        if unit.out_of_sequence or unit.unit_id in jumps:
            found.append(OutOfSequenceIssue())
        if unit.unit_id in duplicates:
            found.append(duplicates[unit.unit_id])
        if unit.unit_id in next_missing:
            found.append(next_missing[unit.unit_id])
        if unit.unit_type == LegalUnitType.CASSATION_DECISION:
            missing = [
                f
                for f in _CASE_FIELDS
                if not unit.metadata.get(f)
                and not (f == "respondent" and unit.no_respondent)
            ]
            if missing:
                found.append(
                    MissingFieldsIssue(
                        fields=missing, searched_lines=_header_search_lines(unit)
                    )
                )
        issues[unit.unit_id] = found
    return issues


def _path(unit: LegalUnit) -> list[SplitPathCrumb]:
    path: list[SplitPathCrumb] = []
    for level, label in unit.crumbs:
        known = _PATH_LEVELS.get(level)
        if known is not None:
            path.append(SplitPathCrumb(level=known, label=label))
    return path


def _preview_unit(
    unit: LegalUnit,
    source_name: str,
    issues: list[SplitPreviewIssue],
    budget: TextBudget,
) -> SplitPreviewUnit:
    text, truncated = budget.take(unit.text)
    metadata = unit.metadata
    return SplitPreviewUnit(
        unit_id=unit.unit_id,
        unit_type=_UNIT_TYPES[unit.unit_type],
        file_name=unit_file_name(source_name, unit.unit_id),
        label=unit.label,
        heading=unit.heading,
        number=unit.number,
        number_text=unit.number_text or None,
        header_start=unit.header_start,
        header_lines=unit.header_lines,
        path=_path(unit),
        case_number=metadata.get("case_number"),
        date=metadata.get("date"),
        applicant=metadata.get("applicant"),
        respondent=metadata.get("respondent"),
        chars=len(unit.text),
        text=text,
        text_truncated=truncated,
        issues=issues,
    )


def _shared_value(units: list[LegalUnit], key: str) -> str | None:
    values = {unit.metadata.get(key) for unit in units}
    if len(values) == 1:
        value = values.pop()
        return value or None
    return None


def _kept_whole(kept: KeptWhole) -> SplitKeptWhole:
    suggested = kept.suggested_profile
    return SplitKeptWhole(
        reason=kept.reason,
        found=kept.found,
        minimum=kept.minimum,
        suggested_profile=(
            "proclamation"
            if suggested == SplitProfile.PROCLAMATION
            else "civil_code"
            if suggested == SplitProfile.CIVIL_CODE
            else "cassation"
            if suggested == SplitProfile.CASSATION
            else None
        ),
    )


def build_split_preview(
    planned: PlannedSplit,
    *,
    size_bytes: int,
    requested_profile: SplitProfile,
    budget: TextBudget,
) -> SplitPreviewSource:
    result = planned.result
    units = result.units
    issues = _issues_for(units)
    articles = [u for u in units if _is_article(u)]
    decisions = [u for u in units if u.unit_type == LegalUnitType.CASSATION_DECISION]
    return SplitPreviewSource(
        source_name=planned.source_name,
        size_bytes=size_bytes,
        splittable=True,
        requested_profile=_PROFILE_NAMES[requested_profile],
        profile=_PROFILE_NAMES[result.profile] if units else "none",
        kept_whole=_kept_whole(result.kept_whole) if result.kept_whole else None,
        law=articles[0].metadata.get("law") if articles else None,
        court=_shared_value(decisions, "court") if decisions else None,
        volume=_shared_value(decisions, "volume") if decisions else None,
        unit_count=len(units),
        article_count=sum(
            1 for u in units if u.unit_type != LegalUnitType.FRONT_MATTER
        ),
        units=[
            _preview_unit(unit, planned.source_name, issues[unit.unit_id], budget)
            for unit in units
        ],
    )


def whole_file_preview(
    file_name: str,
    *,
    size_bytes: int,
    requested_profile: SplitProfile,
    splittable: bool,
) -> SplitPreviewSource:
    """A source that is imported as one document without running the splitter."""
    return SplitPreviewSource(
        source_name=file_name,
        size_bytes=size_bytes,
        splittable=splittable,
        requested_profile=_PROFILE_NAMES[requested_profile],
        profile="none",
        kept_whole=None if splittable else SplitKeptWhole(reason="unsupported_type"),
        law=None,
        court=None,
        volume=None,
        unit_count=0,
        article_count=0,
        units=[],
    )

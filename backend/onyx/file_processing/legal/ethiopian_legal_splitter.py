"""Split Ethiopian legal texts into one unit per article or per cassation decision.

Pure text processing: no I/O, no database, no LLM calls. The File connector upload
route stores each returned `LegalUnit` as its own markdown file, so a chunk never
spans two articles or two decisions.

Supported layouts:
- Proclamations (e.g. the Revised Family Code): article lines such as
  "አንቀጽ ፯ ዕድሜ" under ምዕራፍ / ክፍል / ንዑስ ክፍል headings. A proclamation without
  አንቀጽ lines falls back to numbered headings such as "፩. አጭር ርዕስ".
- Civil Code books: hierarchy lines (መጽሐፍ / አንቀጽ / ምዕራፍ / ክፍል / ንዑስ ክፍል) and
  article lines that start with ቍ or ቁ plus a number (e.g. "ቍ ፰፻፳፮ ...").
- Federal Supreme Court cassation volumes: each decision starts with a case-number
  line (e.g. "የሰበር መዝገብ ቁጥር 94952", "የሰ/መ/ቁ 20938") that is followed by the
  judges, applicant or respondent lines.

Unit text keeps the original lines. Cleaning is applied only to detect headers.
"""

import bisect
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

MIN_UNITS_FOR_SPLIT = 2
MIN_ARTICLES_FOR_AUTO = 10
MIN_CASES_FOR_CASSATION = 2

_MAX_HEADING_CHARS = 60
_MAX_LABEL_CHARS = 40
_MAX_PARTY_CHARS = 40
_MAX_LAW_NAME_CHARS = 80
_MAX_HIERARCHY_LINE_CHARS = 120
_MAX_CASE_HEADER_CHARS = 80
_MAX_ARTICLE_LINE_CHARS = 200
_MAX_NUMBERED_HEADING_CHARS = 60
_CASE_CONFIRM_WINDOW = 10
# Lines in a decision's header block (date, judges) are short.
_MAX_HEADER_BLOCK_LINE_CHARS = 150
# Non-empty lines searched for the parties. The block usually ends earlier, at
# the "መዝገቡ ተመርምሮ" or "ፍርድ" line.
_CASE_HEADER_FIELD_WINDOW = 40
_MAX_PARTY_LINE_CHARS = 200

COURT_NAME = "የፌዴራል ጠቅላይ ፍርድ ቤት ሰበር ሰሚ ችሎት"


class SplitProfile(str, Enum):
    AUTO = "auto"
    PROCLAMATION = "proclamation"
    CIVIL_CODE = "civil_code"
    CASSATION = "cassation"
    NONE = "none"

    @classmethod
    def parse(cls, value: str | None) -> "SplitProfile":
        normalized = (value or cls.NONE.value).strip().lower().replace("-", "_")
        try:
            return cls(normalized)
        except ValueError as e:
            raise ValueError(f"Unknown split profile: {value!r}") from e


class LegalUnitType(str, Enum):
    PROCLAMATION_ARTICLE = "proclamation_article"
    CIVIL_CODE_ARTICLE = "civil_code_article"
    CASSATION_DECISION = "cassation_decision"
    FRONT_MATTER = "front_matter"


@dataclass
class LegalUnit:
    # ASCII and unique within one source file, e.g. "art-7", "case-94952".
    unit_id: str
    unit_type: LegalUnitType
    # Context breadcrumb. Becomes the document title, which prefixes every chunk.
    title: str
    # Short name for lists and citations.
    display_name: str
    # The original lines of the unit.
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # Review fields. They are not metadata, because metadata becomes document tags.
    # "አንቀጽ ፯", "ሰበር መ/ቁ 94952", or "" for front matter.
    label: str = ""
    # Article heading without the law name, e.g. "ዕድሜ".
    heading: str = ""
    number: int | None = None
    # The article number as stored, in the numeral system of the source.
    number_text: str = ""
    # The header's first line in `text`, and how many lines it spans.
    header_start: int = 0
    header_lines: int = 0
    # (level, crumb) pairs, e.g. ("chapter", "ምዕራፍ አንድ ስለ ጋብቻ አፈጻጸም").
    crumbs: list[tuple[str, str]] = field(default_factory=list)
    # The number as written in the source, when the splitter repaired it.
    repaired_from: str | None = None
    out_of_sequence: bool = False
    # Decisions: raw lines of `text` searched for the date and parties.
    details_lines: int = 0
    # Decisions: the header names no respondent ("ተጠሪ፡- የለም", or no ተጠሪ line).
    no_respondent: bool = False


KeptWholeReason = Literal["auto_too_few", "too_few_units"]


@dataclass
class KeptWhole:
    """Why a splittable file stays one document."""

    reason: KeptWholeReason
    found: int
    minimum: int
    # A profile that would split the file, when one exists.
    suggested_profile: SplitProfile | None = None


@dataclass
class SplitResult:
    # The profile that was applied. AUTO is resolved to a concrete profile or NONE.
    profile: SplitProfile
    # Empty when the text should stay whole.
    units: list[LegalUnit]
    warnings: list[str] = field(default_factory=list)
    kept_whole: KeptWhole | None = None


# --- Numbers ---------------------------------------------------------------

_GEEZ_ONES = {ch: i for i, ch in enumerate("፩፪፫፬፭፮፯፰፱", start=1)}
_GEEZ_TENS = {ch: i * 10 for i, ch in enumerate("፲፳፴፵፶፷፸፹፺", start=1)}
_GEEZ_HUNDRED = "፻"
_GEEZ_TEN_THOUSAND = "፼"
_AMHARIC_THOUSAND = "ሺ"
_GEEZ_ONES_BY_VALUE = {v: k for k, v in _GEEZ_ONES.items()}
_GEEZ_TENS_BY_VALUE = {v: k for k, v in _GEEZ_TENS.items()}


def geez_numeral_to_int(numeral: str) -> int:
    """Convert a Ge'ez numeral such as "፰፻፳፮" to 826."""
    total = 0
    group = 0
    current = 0
    for ch in numeral:
        if ch in _GEEZ_ONES:
            current += _GEEZ_ONES[ch]
        elif ch in _GEEZ_TENS:
            current += _GEEZ_TENS[ch]
        elif ch == _GEEZ_HUNDRED:
            group += (current or 1) * 100
            current = 0
        elif ch == _GEEZ_TEN_THOUSAND:
            total = (total + group + current or 1) * 10000
            group = 0
            current = 0
        else:
            raise ValueError(f"Not a Ge'ez numeral character: {ch!r}")
    return total + group + current


def int_to_geez_numeral(value: int) -> str:
    """Render 323 as "፫፻፳፫". Keeps an explicit ፩ before ፻, as the gazettes do."""
    if value <= 0:
        raise ValueError(f"Ge'ez numerals start at 1, got {value}")

    def below_hundred(n: int) -> str:
        return _GEEZ_TENS_BY_VALUE.get(n // 10 * 10, "") + _GEEZ_ONES_BY_VALUE.get(
            n % 10, ""
        )

    if value >= 10000:
        return (
            int_to_geez_numeral(value // 10000)
            + _GEEZ_TEN_THOUSAND
            + (int_to_geez_numeral(value % 10000) if value % 10000 else "")
        )
    hundreds, rest = divmod(value, 100)
    head = below_hundred(hundreds) + _GEEZ_HUNDRED if hundreds else ""
    return head + below_hundred(rest)


def parse_legal_number(token: str) -> int:
    """Parse "፰፻፳፮", "826", "፩ሺ፸", "ሺ 121" or "ሺ" into an int."""
    token = re.sub(r"\s+", "", token)
    if not token:
        raise ValueError("Empty number")
    if _AMHARIC_THOUSAND in token:
        left, _, right = token.partition(_AMHARIC_THOUSAND)
        thousands = parse_legal_number(left) if left else 1
        return thousands * 1000 + (parse_legal_number(right) if right else 0)
    if token.isascii() and token.isdigit():
        return int(token)
    return geez_numeral_to_int(token)


def _format_number_like(raw: str, value: int) -> str:
    """Show a number in the numeral system the source used."""
    raw = raw.strip()
    return str(value) if raw.isascii() and raw.isdigit() else int_to_geez_numeral(value)


# --- Text cleaning ---------------------------------------------------------

_MARKDOWN_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~<])")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")
_EMPHASIS_RE = re.compile(r"[*_]{1,3}")
_SPACES_RE = re.compile(r"[ \t ​]+")


def clean_line(line: str) -> str:
    """Normalize one line for header matching. Never used for stored text."""
    line = _MARKDOWN_ESCAPE_RE.sub(r"\1", line)
    line = _MARKDOWN_HEADING_RE.sub("", line.strip())
    line = _EMPHASIS_RE.sub("", line)
    return _SPACES_RE.sub(" ", line).strip()


def _shorten(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    space = cut.rfind(" ")
    if space > max_chars // 2:
        cut = cut[:space]
    return cut.rstrip() + "…"


def _strip_edge_punctuation(text: str) -> str:
    return text.strip(" .,:;፡።፦-–—…)(/\\_|{}")


_UNIT_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9\-]")


def _make_unique_id(base: str, used: dict[str, int]) -> str:
    base = _UNIT_ID_SAFE_RE.sub("-", base).strip("-") or "unit"
    count = used.get(base, 0)
    used[base] = count + 1
    return base if count == 0 else f"{base}-{count + 1}"


@dataclass
class _Line:
    index: int  # position in the raw line list
    clean: str


def _non_empty_lines(raw_lines: list[str]) -> list[_Line]:
    lines = []
    for index, raw in enumerate(raw_lines):
        cleaned = clean_line(raw)
        if cleaned:
            lines.append(_Line(index=index, clean=cleaned))
    return lines


def _slice_text(raw_lines: list[str], start: int, end: int) -> str:
    return "\n".join(line.rstrip() for line in raw_lines[start:end]).strip("\n")


# --- Article headers -------------------------------------------------------

# Ethiopic and OCR punctuation between a marker and its number: "አንቀፅ ፤ ፫".
_SEP = r"[\s.,:;፡።፤፣፦'\"`“”‘’_\-/()]*"
_GEEZ_RUN = r"[፩-፼]+"
_ARTICLE_NUMBER = rf"(?:{_GEEZ_RUN}\s*ሺ\s*(?:{_GEEZ_RUN}|\d{{1,3}})?|ሺ\s*(?:{_GEEZ_RUN}|\d{{1,3}})?|{_GEEZ_RUN}|\d{{1,4}})"

# Proclamation article: "አንቀጽ ፯ ዕድሜ". The number may sit on the next line.
# "አንቀጽ", also as OCR damages it: "ንቀጽ", "አአንቀፅ", "እንቀፅ", "አንቀቀፅ", "አንበፅ", "አንቀፆ".
_ARTICLE_WORD = r"(?:[አእ]{1,2}ን|ን)(?:ቀ{1,2}|በ)[ጽፅፀፆ]"
_PROCLAMATION_ARTICLE_RE = re.compile(
    rf"^{_ARTICLE_WORD}{_SEP}(?P<num>{_ARTICLE_NUMBER})(?P<rest>.*)$"
)
_BARE_ARTICLE_WORD_RE = re.compile(rf"^{_ARTICLE_WORD}\s*[.:፡]?$")
_LEADING_NUMBER_RE = re.compile(rf"^(?P<num>{_ARTICLE_NUMBER})(?P<rest>.*)$")
# "አንቀጽ ፳ ንዑስ አንቀጽ (፫) ..." is a cross-reference, not a header.
_CROSS_REFERENCE_RE = re.compile(r"^\s*(?:ን[ዑኡ]ስ|(?:እና|ና|እስከ)(?=[\s፩-፼\d]|$)|፣|,)")

# Civil Code article: "ቍ ፰፻፳፮ ...".
_CIVIL_ARTICLE_RE = re.compile(
    rf"^{_SEP}[ቍቁ](?=[\s.,:;፡።\-/]|[፩-፼]|\d|ሺ){_SEP}(?P<num>{_ARTICLE_NUMBER})(?P<rest>.*)$"
)
# OCR sometimes drops the ቍ; accepted only when the number fits the sequence.
_CIVIL_BARE_ARTICLE_RE = re.compile(
    rf"^[\s.,:;፡።\-/]*(?P<num>ሺ\s*(?:{_GEEZ_RUN}|\d{{1,3}})|[፩-፼]{{2,}})(?P<rest>(?:[^፩-፼\d].*)?)$"
)

# Proclamation without አንቀጽ lines: "፩. አጭር ርዕስ".
_NUMBERED_HEADING_RE = re.compile(r"^(?P<num>[፩-፼]+)\s*[.‧]\s*(?P<rest>\S.*)$")
_SENTENCE_END_RE = re.compile(r"(?:።|፡፡|:|፡|;|፤)\s*$")

# OCR leftovers right after a damaged numeral, e.g. "፩፻ሀ", "፩፻ወ፯", "፩፻፷;".
_OCR_NUMBER_TAIL_RE = re.compile(r"^[ሀ-ፚ][፩-፼]*(?=\s|$)")


@dataclass
class _ArticleHeader:
    line: _Line
    raw_number: str
    heading: str
    strong: bool  # True when the article marker (አንቀጽ, ቍ) is on the line
    number: int | None = None
    repaired: bool = False
    out_of_sequence: bool = False
    header_lines: int = 1  # 2 when "አንቀጽ" and the number sit on separate lines
    # Raw index of the header's last line; differs from line.index for 2-line headers.
    last_line_index: int | None = None


def _parse_number_or_none(token: str) -> int | None:
    try:
        return parse_legal_number(token)
    except ValueError:
        return None


def _longest_ordered_indices(values: list[int], strict: bool) -> set[int]:
    """Indices of one longest increasing (strict) or non-decreasing subsequence."""
    find = bisect.bisect_left if strict else bisect.bisect_right
    tail_values: list[int] = []
    tail_indices: list[int] = []
    previous = [-1] * len(values)
    for i, value in enumerate(values):
        pos = find(tail_values, value)
        if pos > 0:
            previous[i] = tail_indices[pos - 1]
        if pos == len(tail_values):
            tail_values.append(value)
            tail_indices.append(i)
        else:
            tail_values[pos] = value
            tail_indices[pos] = i
    result: set[int] = set()
    k = tail_indices[-1] if tail_indices else -1
    while k != -1:
        result.add(k)
        k = previous[k]
    return result


def _assign_article_numbers(headers: list[_ArticleHeader]) -> None:
    """Fix OCR-corrupted numbers: keep the longest ordered run, fill the gaps."""
    parsed = [h for h in headers if h.number is not None]
    anchors_idx = _longest_ordered_indices(
        [h.number for h in parsed if h.number is not None], strict=False
    )
    anchors = {id(parsed[i]) for i in anchors_idx}

    i = 0
    while i < len(headers):
        if id(headers[i]) in anchors:
            i += 1
            continue
        j = i
        while j < len(headers) and id(headers[j]) not in anchors:
            j += 1
        before = headers[i - 1].number if i > 0 else None
        after = headers[j].number if j < len(headers) else None
        run = headers[i:j]
        start: int | None = None
        if before is not None and after is not None:
            if before + len(run) < after:
                start = before + 1
        elif before is not None:
            start = before + 1
        elif after is not None and after - len(run) >= 1:
            start = after - len(run)
        for offset, header in enumerate(run):
            if start is not None:
                new_number = start + offset
                if header.number != new_number:
                    header.repaired = True
                header.number = new_number
            else:
                header.out_of_sequence = True
        i = j


# The ")" of a parenthesized number, which the number pattern leaves behind.
_LEFTOVER_PAREN_RE = re.compile(r"^\)\s*")
# Like _strip_edge_punctuation, but keeps parentheses: "(፪) ..." is a sub-article mark.
_HEADING_EDGE_CHARS = " .,:;፡።፦-–—…/\\_|{}"


def _heading_from_rest(rest: str, header: _ArticleHeader) -> str:
    rest = _LEFTOVER_PAREN_RE.sub("", rest.strip())
    if header.repaired:
        rest = _OCR_NUMBER_TAIL_RE.sub("", rest).strip()
    return rest.strip(_HEADING_EDGE_CHARS)


def _find_proclamation_headers(lines: list[_Line]) -> list[_ArticleHeader]:
    headers: list[_ArticleHeader] = []
    skip_next = False
    for position, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        text = line.clean
        if len(text) > _MAX_ARTICLE_LINE_CHARS:
            continue
        header_lines = 1
        match = _PROCLAMATION_ARTICLE_RE.match(text)
        if (
            not match
            and _BARE_ARTICLE_WORD_RE.match(text)
            and position + 1 < len(lines)
        ):
            match = _LEADING_NUMBER_RE.match(lines[position + 1].clean)
            header_lines = 2
        if not match or _CROSS_REFERENCE_RE.match(match.group("rest")):
            continue
        headers.append(
            _ArticleHeader(
                line=line,
                raw_number=match.group("num"),
                heading=match.group("rest"),
                strong=True,
                number=_parse_number_or_none(match.group("num")),
                header_lines=header_lines,
                last_line_index=lines[position + 1].index
                if header_lines == 2
                else None,
            )
        )
        skip_next = header_lines == 2

    _assign_article_numbers(headers)
    # An out-of-sequence line that reads like a sentence is a body line.
    return [
        h
        for h in headers
        if not (h.out_of_sequence and _SENTENCE_END_RE.search(h.heading))
    ]


def _find_numbered_headings(lines: list[_Line]) -> list[_ArticleHeader]:
    candidates: list[_ArticleHeader] = []
    for line in lines:
        match = _NUMBERED_HEADING_RE.match(line.clean)
        if not match:
            continue
        rest = match.group("rest").strip()
        if len(rest) > _MAX_NUMBERED_HEADING_CHARS or _SENTENCE_END_RE.search(rest):
            continue
        number = _parse_number_or_none(match.group("num"))
        if number is None:
            continue
        candidates.append(
            _ArticleHeader(
                line=line,
                raw_number=match.group("num"),
                heading=rest,
                strong=False,
                number=number,
            )
        )
    keep = _longest_ordered_indices([h.number or 0 for h in candidates], strict=True)
    return [h for i, h in enumerate(candidates) if i in keep]


def _find_civil_code_headers(lines: list[_Line]) -> list[_ArticleHeader]:
    prefixed: list[_ArticleHeader] = []
    bare: list[_ArticleHeader] = []
    for line in lines:
        text = line.clean
        if len(text) > _MAX_ARTICLE_LINE_CHARS:
            continue
        match = _CIVIL_ARTICLE_RE.match(text)
        if match:
            prefixed.append(
                _ArticleHeader(
                    line=line,
                    raw_number=match.group("num"),
                    heading=match.group("rest"),
                    strong=True,
                    number=_parse_number_or_none(match.group("num")),
                )
            )
            continue
        bare_match = _CIVIL_BARE_ARTICLE_RE.match(text)
        if bare_match and not _match_hierarchy(text, include_article_marker=True):
            number = _parse_number_or_none(bare_match.group("num"))
            if number is not None:
                bare.append(
                    _ArticleHeader(
                        line=line,
                        raw_number=bare_match.group("num"),
                        heading=bare_match.group("rest"),
                        strong=False,
                        number=number,
                    )
                )

    _assign_article_numbers(prefixed)
    anchors = [h for h in prefixed if not h.out_of_sequence]
    positions = [h.line.index for h in anchors]
    accepted: list[_ArticleHeader] = []
    for header in bare:
        idx = bisect.bisect_left(positions, header.line.index)
        before = anchors[idx - 1].number if idx > 0 else None
        after = anchors[idx].number if idx < len(anchors) else None
        if (
            before is not None
            and after is not None
            and header.number is not None
            and before < header.number < after
        ):
            accepted.append(header)
    return sorted(prefixed + accepted, key=lambda h: h.line.index)


def count_proclamation_articles(text: str) -> int:
    lines = _non_empty_lines(text.splitlines())
    headers = _find_proclamation_headers(lines)
    if len(headers) >= MIN_UNITS_FOR_SPLIT:
        return len(headers)
    return len(_find_numbered_headings(lines))


def count_civil_code_articles(text: str) -> int:
    lines = _non_empty_lines(text.splitlines())
    return sum(1 for h in _find_civil_code_headers(lines) if h.strong)


# --- Hierarchy (book / part / chapter / section / subsection) --------------

_ONES_WORD = r"(?:አንደኛ|አንድ|ሁለተኛ|ሁለት|ሦስተኛ|ሶስተኛ|ሦስት|ሶስት|አራተኛ|አራት|አምስተኛ|አምስት|ስድስተኛ|ስድስት|ሰባተኛ|ሰባት|ስምንተኛ|ስምንት|ዘጠነኛ|ዘጠኝ)"
_TENS_WORD = (
    r"(?:አሥረኛ|አስረኛ|አሥራ|አስራ|አሥር|አስር|ሃያ|ሀያ|ሠላሳ|ሰላሳ|አርባ|ሃምሳ|ሀምሳ|ስልሳ|ሥልሳ|ሰባ|ሰማንያ|ዘጠና)"
)
_NUMBER_WORDS = rf"(?:{_TENS_WORD}(?:\s*{_ONES_WORD})?|{_ONES_WORD})"

_HIERARCHY_RE = re.compile(
    rf"^(?P<marker>መጽሐፍ|አንቀ[ጽፅ]|ምዕራፍ|ን[ዑኡ]ስ\s*ክፍል|ክፍል){_SEP}"
    rf"(?P<num>{_GEEZ_RUN}|\d{{1,3}}|{_NUMBER_WORDS})(?=[\s.,:;፡።\-/()]|$)(?P<rest>.*)$"
)

_HIERARCHY_METADATA_KEYS = {
    "መጽሐፍ": "book",
    "አንቀጽ": "part",
    "ምዕራፍ": "chapter",
    "ክፍል": "section",
    "ንዑስ ክፍል": "subsection",
}


@dataclass
class _HierarchyMatch:
    marker: str  # normalized marker, a key of _HIERARCHY_METADATA_KEYS
    label: str  # e.g. "ምዕራፍ አንድ"
    title: str  # inline title, may be empty


def _match_hierarchy(text: str, include_article_marker: bool) -> _HierarchyMatch | None:
    if len(text) > _MAX_HIERARCHY_LINE_CHARS or _SENTENCE_END_RE.search(text):
        return None
    match = _HIERARCHY_RE.match(text)
    if not match:
        return None
    marker = match.group("marker")
    if marker.startswith("ን"):
        marker = "ንዑስ ክፍል"
    elif marker.startswith("አንቀ"):
        if not include_article_marker:
            return None
        marker = "አንቀጽ"
    label = f"{marker} {match.group('num').strip()}"
    title = _strip_edge_punctuation(match.group("rest"))
    return _HierarchyMatch(marker=marker, label=label, title=title)


class _Hierarchy:
    """Current breadcrumb. Levels are ranked by first appearance in the text."""

    def __init__(self) -> None:
        self._rank: dict[str, float] = {}
        self._crumbs: dict[str, tuple[float, str]] = {}

    def _rank_of(self, marker: str) -> float:
        if marker not in self._rank:
            if marker == "ንዑስ ክፍል" and "ክፍል" in self._rank:
                self._rank[marker] = self._rank["ክፍል"] + 0.5
            else:
                self._rank[marker] = float(
                    max((int(r) for r in self._rank.values()), default=-1) + 1
                )
        return self._rank[marker]

    def enter(self, match: _HierarchyMatch) -> None:
        rank = self._rank_of(match.marker)
        self._crumbs = {k: v for k, v in self._crumbs.items() if v[0] < rank}
        self._crumbs[match.marker] = (rank, _join_label(match.label, match.title))

    def set_title(self, marker: str, title: str) -> None:
        if marker in self._crumbs:
            rank, label = self._crumbs[marker]
            self._crumbs[marker] = (rank, _join_label(label, title))

    def crumbs(self) -> list[tuple[str, str]]:
        ordered = sorted(self._crumbs.items(), key=lambda kv: kv[1][0])
        return [(marker, text) for marker, (_, text) in ordered]


def _join_label(label: str, title: str) -> str:
    return _shorten(f"{label} {title}".strip(), _MAX_LABEL_CHARS)


# --- Article splitting -------------------------------------------------------


def _resolve_law_name(
    lines: list[_Line], law_name: str | None, source_name: str, first_boundary: int
) -> str:
    if law_name and law_name.strip():
        return _shorten(law_name, _MAX_LAW_NAME_CHARS)
    for line in lines:
        if line.index >= first_boundary:
            break
        if len(line.clean) <= 150:
            return _shorten(_strip_edge_punctuation(line.clean), _MAX_LAW_NAME_CHARS)
        break
    return _source_stem(source_name)


def _source_stem(source_name: str) -> str:
    base = source_name.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0] if "." in base else base


def _split_articles(
    text: str,
    profile: SplitProfile,
    law_name: str | None,
    source_name: str,
) -> list[LegalUnit]:
    raw_lines = text.splitlines()
    lines = _non_empty_lines(raw_lines)

    if profile == SplitProfile.CIVIL_CODE:
        headers = _find_civil_code_headers(lines)
        unit_type = LegalUnitType.CIVIL_CODE_ARTICLE
        article_word = "ቍ"
        include_article_marker = True
    else:
        headers = _find_proclamation_headers(lines)
        if len(headers) < MIN_UNITS_FOR_SPLIT:
            headers = _find_numbered_headings(lines)
        unit_type = LegalUnitType.PROCLAMATION_ARTICLE
        article_word = "አንቀጽ"
        include_article_marker = False
    if not headers:
        return []

    header_by_line = {h.line.index: h for h in headers}
    hierarchy_by_line: dict[int, _HierarchyMatch] = {}
    for line in lines:
        if line.index in header_by_line:
            continue
        match = _match_hierarchy(line.clean, include_article_marker)
        if match:
            hierarchy_by_line[line.index] = match

    first_boundary = min(
        [headers[0].line.index, *hierarchy_by_line.keys()],
    )
    law = _resolve_law_name(lines, law_name, source_name, first_boundary)

    units: list[LegalUnit] = []
    used_ids: dict[str, int] = {}
    hierarchy = _Hierarchy()

    front_matter = _slice_text(raw_lines, 0, first_boundary)
    if front_matter.strip():
        units.append(
            LegalUnit(
                unit_id=_make_unique_id("front-matter", used_ids),
                unit_type=LegalUnitType.FRONT_MATTER,
                title=f"{law} › መግቢያ",
                display_name=f"መግቢያ — {law}",
                text=front_matter,
                metadata={
                    "legal_unit_type": LegalUnitType.FRONT_MATTER.value,
                    "law": law,
                },
            )
        )

    # Walk the non-empty lines once and cut a unit at every article header and
    # every hierarchy line. Hierarchy lines and their titles belong to no unit.
    current: _ArticleHeader | None = None
    current_start = 0
    current_crumbs: list[tuple[str, str]] = []
    pending_lines: list[int] = []  # orphan lines after a hierarchy heading
    pending_title_marker: str | None = None

    def flush(end: int) -> None:
        nonlocal current
        if current is None:
            return
        body = _slice_text(raw_lines, current_start, end)
        last_line = current.last_line_index or current.line.index
        units.append(
            _build_article_unit(
                current,
                body,
                current_crumbs,
                law,
                article_word,
                unit_type,
                used_ids,
                header_start=current.line.index - current_start,
                header_span=last_line - current.line.index + 1,
            )
        )
        current = None

    line_positions = {line.index: pos for pos, line in enumerate(lines)}
    skip_until = -1
    for line in lines:
        if line.index <= skip_until:
            continue
        header = header_by_line.get(line.index)
        if header is not None:
            flush(line.index)
            current = header
            # Orphan lines after a hierarchy heading open the next article.
            current_start = pending_lines[0] if pending_lines else line.index
            pending_lines = []
            pending_title_marker = None
            current_crumbs = hierarchy.crumbs()
            if header.header_lines == 2:
                position = line_positions[line.index]
                skip_until = lines[position + 1].index
            continue

        match = hierarchy_by_line.get(line.index)
        if match is not None:
            flush(line.index)
            hierarchy.enter(match)
            pending_title_marker = None if match.title else match.marker
            pending_lines = []
            continue

        if pending_title_marker is not None:
            if len(line.clean) <= _MAX_HIERARCHY_LINE_CHARS:
                hierarchy.set_title(pending_title_marker, line.clean)
                pending_title_marker = None
                continue
            pending_title_marker = None

        if current is None and line.index >= first_boundary:
            pending_lines.append(line.index)

    flush(len(raw_lines))
    return units


def _build_article_unit(
    header: _ArticleHeader,
    body: str,
    crumbs: list[tuple[str, str]],
    law: str,
    article_word: str,
    unit_type: LegalUnitType,
    used_ids: dict[str, int],
    header_start: int = 0,
    header_span: int = 1,
) -> LegalUnit:
    number = header.number
    number_text = (
        _format_number_like(header.raw_number, number)
        if number is not None
        else header.raw_number.strip() or "?"
    )
    heading = _shorten(_heading_from_rest(header.heading, header), _MAX_HEADING_CHARS)
    label = f"{article_word} {number_text}"
    labelled = f"{label} {heading}".strip()

    metadata = {
        "legal_unit_type": unit_type.value,
        "law": law,
        "article": str(number) if number is not None else number_text,
    }
    for marker, crumb in crumbs:
        metadata[_HIERARCHY_METADATA_KEYS[marker]] = crumb

    warnings: list[str] = []
    snippet = _shorten(header.line.clean, 60)
    if header.repaired:
        warnings.append(
            f"article number repaired from {header.raw_number.strip()} to {number_text}: {snippet}"
        )
    if header.out_of_sequence:
        warnings.append(f"article number out of sequence: {snippet}")

    unit_base = f"art-{number}" if number is not None else "art"
    return LegalUnit(
        unit_id=_make_unique_id(unit_base, used_ids),
        unit_type=unit_type,
        title=" › ".join([law, *(crumb for _, crumb in crumbs), labelled]),
        display_name=f"{labelled} — {law}",
        text=body,
        metadata=metadata,
        warnings=warnings,
        label=label,
        heading=heading,
        number=number,
        number_text=number_text,
        header_start=header_start,
        header_lines=header_span,
        crumbs=[(_HIERARCHY_METADATA_KEYS[marker], crumb) for marker, crumb in crumbs],
        repaired_from=header.raw_number.strip() if header.repaired else None,
        out_of_sequence=header.out_of_sequence,
    )


# --- Cassation decisions -----------------------------------------------------

_CASE_HEADER_RE = re.compile(
    r"^[\s/\\*'\"“”‘’▪•·\-]*(?:የ\s*)?"
    r"(?:ሰበር\s*(?:መዝገብ|መዘገብ)\s*ቁጥር|ሰበር\s*መ[\s/.]*ቁ(?:ጥር)?|ሰ[\s/.]*መ[\s/.]*ቁ(?:ጥር)?|መ[\s/.]*ቁ(?:ጥር)?)"
    r"[\s/\\.,*:፡\-]*(?:\d\s*[.,]\s*(?=\d{3}))?(?P<num>\d{3,7})(?P<rest>.*)$"
)
_CASE_CONFIRM_RE = re.compile(r"^(?:ዳኞች|አመልካ|ተጠሪ)")
_VOLUME_RE = re.compile(r"^ቅ[ፅጽ]\s*[-:፡./]*\s*(?P<num>\d{1,3}|[፩-፼]+)\s*$")
_COURT_BANNER_RE = re.compile(
    r"^(?:የፌዴራል\s+ጠቅላይ\s+ፍርድ\s+ቤት\s+ሰበር\s+(?:ሰሚ\s+)?ችሎት|ው[ሳሣ]ኔዎች)\s*[።፡]*$"
)
_ETHIOPIAN_MONTHS = "መስከረም|ጥቅምት|ኅዳር|ኀዳር|ሕዳር|ህዳር|ታኅሣሥ|ታህሳስ|ታሕሳስ|ታህሣሥ|ጥር|የካቲት|መጋቢት|ሚያዝያ|ግንቦት|ሰኔ|ሐምሌ|ሀምሌ|ነሐሴ|ነሀሴ|ጳጉሜ"
_DATE_RE = re.compile(
    rf"(?:{_ETHIOPIAN_MONTHS})|\d{{1,2}}\s*/\s*\d{{1,2}}\s*/\s*\d{{2,4}}|ዓ\s*[./]\s*ም"
)
_APPLICANT_LABEL = r"አመልካ(?:ች|ቾች|ቶች)"
# Older volumes call the respondent "መልስ ሰጭ" or "መ/ሰጭ".
_OLD_RESPONDENT_LABEL = r"(?:መልስ\s*ሰ[ጭጪ]|መ\s*/\s*ሰ[ጭጪ])(?:ዎች)?"
_APPLICANT_RE = re.compile(rf"^{_APPLICANT_LABEL}\s*[፡፦:\-–—.…\s]*(?P<rest>.*)$")
_RESPONDENT_RE = re.compile(
    rf"^(?:ተጠሪ(?:ዎች)?\s*[፡፦:\-–—.…\s]*|{_OLD_RESPONDENT_LABEL}\s*[፡፦:]+[\-–—.…\s]*)(?P<rest>.*)$"
)
# A label inside a line, after other text: "... ቀርበዋል ተጠሪ፡- ወ/ሮ ታደለች ...".
_APPLICANT_INLINE_RE = re.compile(
    rf"(?<!\S){_APPLICANT_LABEL}\s*[፡፦:]+[\-–—.…\s፡፦:]*(?P<rest>.*)$"
)
_RESPONDENT_INLINE_RE = re.compile(
    rf"(?<!\S)(?:ተጠሪ(?:ዎች)?|{_OLD_RESPONDENT_LABEL})\s*[፡፦:]+[\-–—.…\s፡፦:]*(?P<rest>.*)$"
)
# Where an inline value ends: the next label, or the start of the judgment.
_NEXT_FIELD_RE = re.compile(
    rf"(?<!\S)(?:(?:{_APPLICANT_LABEL}|ተጠሪ(?:ዎች)?|{_OLD_RESPONDENT_LABEL})\s*[፡፦:]|መዝገቡ)"
)
_NO_PARTY_RE = re.compile(r"^[\s.…\-–—፡፦:]*የለም")
# Lines that end the parties block of a decision header.
_HEADER_FIELD_RE = re.compile(
    rf"^(?:ዳኞች|አመልካ|ተጠሪ|{_OLD_RESPONDENT_LABEL}|መዝገቡ|ፍ\s*ር\s*ድ)"
)
# The line after the parties: "መዝገቡ ተመርምሮ ...", "ይህ መዝገብ ...", "ፍርድ".
_PARTIES_END_RE = re.compile(r"^(?:መዝገቡ|ይህ\s+መዝገብ|ፍ\s*ር\s*ድ\s*[።፡]*$)")
_JUDGMENT_TITLE_RE = re.compile(r"^ፍ\s*ር\s*ድ\s*[።፡]*$")
_PARTY_NOTE_RE = re.compile(
    r"\s*(?:[-–—]\s*)?(?:ቀረቡ|ቀረበች|ቀረበ|ቀርበዋል|አልቀረቡም|አልቀረበም|የቀረበ|ከ?ጠበቃ|ነገረ\s*ፈጅ|ወኪል|ተወካይ|በእ?ራሳቸው|በእ?ራሱ|በእ?ራሷ).*$"
)
_LIST_NUMBER_RE = re.compile(r"^\d{1,2}\s*(?:[.)]|ኛ)\s*")
# A representative follows the party after a spaced dash: "ወ/ሮ X - ጠበቃ Y".
_PARTY_DASH_RE = re.compile(r"\s[-–—]|[-–—]\s")
# Redacted names are written as a run of dots.
_REDACTION_RE = re.compile(r"[.…]{2,}.*$")
_EMPTY_PARTY_RE = re.compile(r"^(?:አቶ|ወ/ሮ|ወ/ሪት|ወ/ት|ዶ/ር|የለም)?$")


def _confirmed_case_headers(lines: list[_Line]) -> list[tuple[int, str]]:
    """(position in `lines`, case number) for each confirmed decision header.

    A header is confirmed by a judges, applicant or respondent line in the short
    header block that follows it. The block ends at the next header-like line or
    at the first paragraph-length line.
    """
    headers: list[tuple[int, str]] = []
    for position, line in enumerate(lines):
        if len(line.clean) > _MAX_CASE_HEADER_CHARS:
            continue
        match = _CASE_HEADER_RE.match(line.clean)
        if not match:
            continue
        for candidate in lines[position + 1 : position + 1 + _CASE_CONFIRM_WINDOW]:
            if _CASE_CONFIRM_RE.match(candidate.clean):
                headers.append((position, match.group("num")))
                break
            if len(
                candidate.clean
            ) > _MAX_HEADER_BLOCK_LINE_CHARS or _CASE_HEADER_RE.match(candidate.clean):
                break
    return headers


def count_cassation_decisions(text: str) -> int:
    return len(_confirmed_case_headers(_non_empty_lines(text.splitlines())))


def _clean_party(value: str) -> str:
    value = value.strip().lstrip(".…-–—፦: ")
    value = _LIST_NUMBER_RE.sub("", value)
    value = _PARTY_NOTE_RE.sub("", value)
    value = _PARTY_DASH_RE.split(value, maxsplit=1)[0]
    value = _strip_edge_punctuation(_REDACTION_RE.sub("", value))
    if _EMPTY_PARTY_RE.match(value):
        return ""
    return _shorten(value, _MAX_PARTY_CHARS)


@dataclass
class _Party:
    name: str
    # A label for this party is in the header, even when the name is empty.
    labelled: bool
    # The header says there is no such party: "ተጠሪ፡- የለም".
    none: bool


def _find_party(
    lines: list[_Line], pattern: re.Pattern[str], inline: re.Pattern[str]
) -> _Party:
    for index, line in enumerate(lines):
        match = pattern.match(line.clean)
        if match:
            rest = match.group("rest")
        else:
            inline_match = inline.search(line.clean)
            if not inline_match:
                continue
            rest = inline_match.group("rest")
        next_field = _NEXT_FIELD_RE.search(rest)
        if next_field:
            rest = rest[: next_field.start()]
        if (
            not rest.strip(" .…-–—፦:")
            and index + 1 < len(lines)
            and not _HEADER_FIELD_RE.match(lines[index + 1].clean)
        ):
            rest = lines[index + 1].clean
        return _Party(
            name=_clean_party(rest), labelled=True, none=bool(_NO_PARTY_RE.match(rest))
        )
    return _Party(name="", labelled=False, none=False)


def _parties_block(block: list[_Line]) -> list[_Line]:
    """The decision header lines that hold the date and the parties."""
    parties: list[_Line] = []
    for line in block[1 : 1 + _CASE_HEADER_FIELD_WINDOW]:
        if _PARTIES_END_RE.match(line.clean):
            # Some volumes print "ፍ ር ድ" above the judges and parties.
            seen_party = any(
                _APPLICANT_RE.match(p.clean) or _RESPONDENT_RE.match(p.clean)
                for p in parties
            )
            if _JUDGMENT_TITLE_RE.match(line.clean) and not seen_party:
                parties.append(line)
                continue
            break
        is_field = _APPLICANT_RE.match(line.clean) or _RESPONDENT_RE.match(line.clean)
        if len(line.clean) > _MAX_PARTY_LINE_CHARS and not is_field:
            break
        parties.append(line)
    return parties


def _parse_date(lines: list[_Line]) -> str:
    for line in lines[:3]:
        if _DATE_RE.search(line.clean) and len(line.clean) <= _MAX_LABEL_CHARS:
            return _strip_edge_punctuation(line.clean)
    return ""


def _pop_trailing_banner_lines(block: list[_Line]) -> str | None:
    """Drop volume and court banners at the end of a block; return the volume."""
    volume: str | None = None
    while block and (
        _VOLUME_RE.match(block[-1].clean) or _COURT_BANNER_RE.match(block[-1].clean)
    ):
        match = _VOLUME_RE.match(block.pop().clean)
        if match and volume is None:
            volume = match.group("num")
    return volume


def split_cassation_decisions(
    text: str, volume: str | None, source_name: str
) -> list[LegalUnit]:
    raw_lines = text.splitlines()
    lines = _non_empty_lines(raw_lines)
    headers = _confirmed_case_headers(lines)
    if not headers:
        return []

    units: list[LegalUnit] = []
    used_ids: dict[str, int] = {}

    front = lines[: headers[0][0]]
    current_volume = volume
    detected = _pop_trailing_banner_lines(front)
    if current_volume is None and detected is not None:
        current_volume = detected
    front = [line for line in front if not _VOLUME_RE.match(line.clean)]

    # Consecutive blocks with the same number are one decision split by a page break.
    blocks: list[tuple[str, list[_Line]]] = []
    for position, (start, number) in enumerate(headers):
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        if blocks and blocks[-1][0] == number:
            blocks[-1][1].extend(lines[start:end])
        else:
            blocks.append((number, list(lines[start:end])))

    for number, block in blocks:
        block_volume = current_volume
        next_volume = _pop_trailing_banner_lines(block)
        if next_volume is not None and volume is None:
            current_volume = next_volume
        start_index = block[0].index
        end_index = block[-1].index + 1
        body = _slice_text(raw_lines, start_index, end_index)
        units.append(_build_case_unit(number, block, body, block_volume, used_ids))

    if front:
        source_label = _source_stem(source_name)
        units.insert(
            0,
            LegalUnit(
                unit_id=_make_unique_id("front-matter", used_ids),
                unit_type=LegalUnitType.FRONT_MATTER,
                title=f"{source_label} › መግቢያ",
                display_name=f"መግቢያ — {source_label}",
                text=_slice_text(raw_lines, 0, front[-1].index + 1),
                metadata={"legal_unit_type": LegalUnitType.FRONT_MATTER.value},
            ),
        )
    return units


def _build_case_unit(
    number: str,
    block: list[_Line],
    body: str,
    volume: str | None,
    used_ids: dict[str, int],
) -> LegalUnit:
    header_lines = _parties_block(block)
    date = _parse_date(header_lines)
    applicant_party = _find_party(header_lines, _APPLICANT_RE, _APPLICANT_INLINE_RE)
    respondent_party = _find_party(header_lines, _RESPONDENT_RE, _RESPONDENT_INLINE_RE)
    applicant = applicant_party.name
    respondent = respondent_party.name
    # A petition names no respondent: "ተጠሪ፡- የለም", or no ተጠሪ line at all.
    no_respondent = not respondent and (
        respondent_party.none
        or (applicant_party.labelled and not respondent_party.labelled)
    )
    last_line = header_lines[-1] if header_lines else block[0]
    details_lines = last_line.index - block[0].index + 1

    display_name = f"ሰበር መ/ቁ {number}"
    if date:
        display_name += f" ({date})"
    if applicant and respondent:
        display_name += f" — {applicant} v. {respondent}"
    elif applicant:
        display_name += f" — {applicant}"
    title = f"ቅጽ {volume} › {display_name}" if volume else display_name

    metadata = {
        "legal_unit_type": LegalUnitType.CASSATION_DECISION.value,
        "case_number": number,
        "court": COURT_NAME,
    }
    if date:
        metadata["date"] = date
    if volume:
        metadata["volume"] = volume
    if applicant:
        metadata["applicant"] = applicant
    if respondent:
        metadata["respondent"] = respondent

    return LegalUnit(
        unit_id=_make_unique_id(f"case-{number}", used_ids),
        unit_type=LegalUnitType.CASSATION_DECISION,
        title=title,
        display_name=display_name,
        text=body,
        metadata=metadata,
        label=f"ሰበር መ/ቁ {number}",
        header_lines=1,
        details_lines=details_lines,
        no_respondent=no_respondent,
    )


# --- Entry points ------------------------------------------------------------


@dataclass
class ProfileCounts:
    cases: int
    proclamation: int
    civil: int


def profile_counts(text: str) -> ProfileCounts:
    return ProfileCounts(
        cases=count_cassation_decisions(text),
        proclamation=count_proclamation_articles(text),
        civil=count_civil_code_articles(text),
    )


def _detect_from_counts(counts: ProfileCounts) -> SplitProfile:
    if counts.cases >= MIN_CASES_FOR_CASSATION and counts.cases * 5 >= max(
        counts.proclamation, counts.civil
    ):
        return SplitProfile.CASSATION
    if (
        counts.proclamation >= MIN_ARTICLES_FOR_AUTO
        and counts.proclamation >= counts.civil
    ):
        return SplitProfile.PROCLAMATION
    if counts.civil >= MIN_ARTICLES_FOR_AUTO:
        return SplitProfile.CIVIL_CODE
    return SplitProfile.NONE


def detect_profile(text: str) -> SplitProfile:
    return _detect_from_counts(profile_counts(text))


def _auto_too_few(counts: ProfileCounts) -> KeptWhole:
    """Explain why auto did not split, and name a profile that would."""
    candidates = [
        (counts.proclamation, SplitProfile.PROCLAMATION, MIN_UNITS_FOR_SPLIT),
        (counts.civil, SplitProfile.CIVIL_CODE, MIN_UNITS_FOR_SPLIT),
        (counts.cases, SplitProfile.CASSATION, MIN_CASES_FOR_CASSATION),
    ]
    usable = [
        (count, profile) for count, profile, minimum in candidates if count >= minimum
    ]
    suggested = max(usable, key=lambda item: item[0])[1] if usable else None
    return KeptWhole(
        reason="auto_too_few",
        found=max(counts.proclamation, counts.civil, counts.cases),
        minimum=MIN_ARTICLES_FOR_AUTO,
        suggested_profile=suggested,
    )


def split_legal_text(
    text: str,
    profile: SplitProfile,
    source_name: str = "",
    law_name: str | None = None,
    volume: str | None = None,
) -> SplitResult:
    """Split a legal text into units. `units` is empty when the text should stay whole."""
    if profile == SplitProfile.AUTO:
        counts = profile_counts(text)
        profile = _detect_from_counts(counts)
        if profile == SplitProfile.NONE:
            return SplitResult(
                profile=profile, units=[], kept_whole=_auto_too_few(counts)
            )
    if profile == SplitProfile.NONE:
        return SplitResult(profile=profile, units=[])

    if profile == SplitProfile.CASSATION:
        units = split_cassation_decisions(text, volume=volume, source_name=source_name)
    else:
        units = _split_articles(
            text, profile, law_name=law_name, source_name=source_name
        )

    real_units = [u for u in units if u.unit_type != LegalUnitType.FRONT_MATTER]
    if len(real_units) < MIN_UNITS_FOR_SPLIT:
        return SplitResult(
            profile=profile,
            units=[],
            warnings=[
                f"found {len(real_units)} unit(s) with profile {profile.value}; the file stays whole"
            ],
            kept_whole=KeptWhole(
                reason="too_few_units",
                found=len(real_units),
                minimum=MIN_UNITS_FOR_SPLIT,
            ),
        )
    warnings = [w for u in units for w in u.warnings]
    return SplitResult(profile=profile, units=units, warnings=warnings)


def _main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Dry-run the Ethiopian legal splitter."
    )
    parser.add_argument("path")
    parser.add_argument("--profile", default=SplitProfile.AUTO.value)
    parser.add_argument("--law-name")
    parser.add_argument("--volume")
    parser.add_argument("--show", type=int, default=0, help="print the first N units")
    args = parser.parse_args()

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    result = split_legal_text(
        text,
        SplitProfile.parse(args.profile),
        source_name=path.name,
        law_name=args.law_name,
        volume=args.volume,
    )
    print(f"profile={result.profile.value} units={len(result.units)}")
    for unit in result.units:
        print(f"{unit.unit_id:>18}  {len(unit.text):>6} chars  {unit.display_name}")
    for unit in result.units[: args.show]:
        print(f"\n===== {unit.unit_id} | {unit.title}\n{unit.metadata}\n{unit.text}")
    print(f"\nwarnings={len(result.warnings)}")
    for warning in result.warnings:
        print(f"  - {warning}")


if __name__ == "__main__":
    _main()

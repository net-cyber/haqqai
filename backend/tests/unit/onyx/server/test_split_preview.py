"""The split review: every unit with its text, and the issues an admin should check."""

from pathlib import Path

from onyx.file_processing.legal.ethiopian_legal_splitter import SplitProfile
from onyx.server.documents.file_splitting import plan_split
from onyx.server.documents.models import (
    DuplicateNumberIssue,
    MissingFieldsIssue,
    NextMissingIssue,
    NumberRepairedIssue,
    OutOfSequenceIssue,
    SplitPreviewSource,
    SplitPreviewUnit,
)
from onyx.server.documents.split_preview import (
    PREVIEW_EXCERPT_CHARS,
    TextBudget,
    build_split_preview,
)

FIXTURES = Path(__file__).parents[1] / "file_processing" / "legal" / "fixtures"

# Twelve articles under one chapter. Article ፬ appears twice with the same text,
# article ፯ is missing and its heading sits inside article ፮ without its first
# letter, and article ፲'s number reads ፩ in the scan.
PROCLAMATION = """የሙከራ አዋጅ ቁጥር ፩

ምዕራፍ አንድ ጠቅላላ

አንቀጽ ፩ አጭር ርዕስ
ይህ አዋጅ የሙከራ አዋጅ ተብሎ ሊጠቀስ ይችላል።

አንቀጽ ፪ ትርጓሜ
በዚህ አዋጅ ውስጥ ቃላት ትርጉም አላቸው።

አንቀጽ ፫ የተፈጻሚነት ወሰን
ይህ አዋጅ በመላው አገሪቱ ተፈጻሚ ይሆናል።

አንቀጽ ፬ መርሆዎች
መርሆዎቹ እኩልነትና ፍትሕ ናቸው።

አንቀጽ ፬ መርሆዎች
መርሆዎቹ እኩልነትና ፍትሕ ናቸው።

አንቀጽ ፭ መብቶች
ማንኛውም ሰው መብት አለው።

አንቀጽ ፮ ግዴታዎች
ማንኛውም ሰው ግዴታ አለበት።
ንቀጽ ፯ ኃላፊነት
ኃላፊነት በሕግ ይወሰናል።

አንቀጽ ፰ ቅጣት
ቅጣት በሕግ ብቻ ይጣላል።

አንቀጽ ፱ ይግባኝ
ይግባኝ ማቅረብ ይቻላል።

አንቀጽ ፩ ደንብ
ደንብ ሊወጣ ይችላል።

አንቀጽ ፲፩ የተሻሩ ሕጎች
ቀደምት ሕጎች ተሽረዋል።

አንቀጽ ፲፪ የሚጸናበት ጊዜ
ይህ አዋጅ ከታተመበት ቀን ጀምሮ ይጸናል።
"""


def _preview(
    text: str,
    profile: SplitProfile = SplitProfile.PROCLAMATION,
    budget: TextBudget | None = None,
) -> SplitPreviewSource:
    data = text.encode("utf-8")
    return build_split_preview(
        plan_split("law.md", data, profile),
        size_bytes=len(data),
        requested_profile=profile,
        budget=budget or TextBudget(),
    )


def _units(source: SplitPreviewSource) -> dict[str, SplitPreviewUnit]:
    return {unit.unit_id: unit for unit in source.units}


def test_every_unit_is_returned_with_review_fields() -> None:
    source = _preview(PROCLAMATION)
    units = _units(source)

    assert source.law == "የሙከራ አዋጅ ቁጥር ፩"
    assert source.unit_count == len(source.units)
    article = units["art-5"]
    assert (article.label, article.heading, article.number) == ("አንቀጽ ፭", "መብቶች", 5)
    assert article.number_text == "፭"
    assert article.file_name == "law__art-5.md"
    assert [(c.level, c.label) for c in article.path] == [("chapter", "ምዕራፍ አንድ ጠቅላላ")]
    assert article.text.startswith("አንቀጽ ፭ መብቶች")
    assert article.issues == []


def test_repaired_number_is_flagged_with_the_source_heading() -> None:
    issues = _units(_preview(PROCLAMATION))["art-10"].issues
    assert issues == [NumberRepairedIssue(source_number="፩", source_line="አንቀጽ ፩ ደንብ")]


def test_duplicate_numbers_point_at_each_other() -> None:
    units = _units(_preview(PROCLAMATION))
    assert units["art-4"].issues == [
        DuplicateNumberIssue(other_unit_ids=["art-4-2"], differing_chars=0)
    ]
    assert units["art-4-2"].issues == [
        DuplicateNumberIssue(other_unit_ids=["art-4"], differing_chars=0)
    ]


def test_missing_number_is_reported_after_the_previous_article() -> None:
    issues = _units(_preview(PROCLAMATION))["art-6"].issues
    assert issues == [
        NextMissingIssue(
            from_number=7,
            to_number=7,
            from_text="፯",
            to_text="፯",
            suspect_line=2,
            suspect_text="ንቀጽ ፯ ኃላፊነት",
        )
    ]


def test_out_of_sequence_article_is_flagged() -> None:
    # Article ፯ sits between ፫ and ፬, where the sequence has no room for it.
    numbers = ["፩", "፪", "፫", "፯", "፬", "፭", "፮", "፰", "፱", "፲", "፲፩"]
    text = "የሙከራ አዋጅ\n\n" + "\n\n".join(
        f"አንቀጽ {n} ርዕስ {i}\nጽሑፍ {i}።" for i, n in enumerate(numbers)
    )
    units = _units(_preview(text))
    flagged = [u for u in units.values() if OutOfSequenceIssue() in u.issues]
    assert [(u.number, u.heading) for u in flagged] == [(7, "ርዕስ 3")]


def test_auto_explains_why_a_short_law_stays_whole() -> None:
    source = _preview(
        (FIXTURES / "amendment_proc_1070.md").read_text(encoding="utf-8"),
        SplitProfile.AUTO,
    )
    assert source.units == []
    assert source.profile == "none"
    assert source.requested_profile == "auto"
    assert source.kept_whole is not None
    assert source.kept_whole.model_dump() == {
        "reason": "auto_too_few",
        "found": 3,
        "minimum": 10,
        "suggested_profile": "proclamation",
    }


def test_decisions_report_missing_details_and_shared_court() -> None:
    text = (FIXTURES / "cassation_small.md").read_text(encoding="utf-8")
    source = _preview(text, SplitProfile.CASSATION)
    assert source.court == "የፌዴራል ጠቅላይ ፍርድ ቤት ሰበር ሰሚ ችሎት"
    assert source.law is None

    no_respondent = text.replace(
        "ተጠሪ- ወ/ሮ የሺ ውድዬ - ረ/ኢንስፔክተር ይመር ዮሴፍ ቀረቡ፡፡", "ተጠሪ- የለም"
    )
    assert no_respondent != text
    units = _units(_preview(no_respondent, SplitProfile.CASSATION))
    (issue,) = units["case-94952"].issues
    assert isinstance(issue, MissingFieldsIssue)
    assert issue.fields == ["respondent"]
    # The window is the header line plus up to 15 non-empty lines, blank lines
    # included, and it never runs past the end of the decision.
    lines = units["case-94952"].text.split("\n")
    non_empty = sum(1 for line in lines[: issue.searched_lines] if line.strip())
    assert 0 < issue.searched_lines <= len(lines)
    assert non_empty == min(16, sum(1 for line in lines if line.strip()))
    assert units["case-94952"].respondent is None


def test_text_budget_sends_excerpts_once_spent() -> None:
    budget = TextBudget(total_chars=100)
    source = _preview(PROCLAMATION * 30, budget=budget)
    assert budget.exceeded
    truncated = [u for u in source.units if u.text_truncated]
    assert truncated
    assert all(len(u.text) <= PREVIEW_EXCERPT_CHARS for u in truncated)
    assert all(u.chars >= len(u.text) for u in source.units)


def test_implausible_number_jump_is_out_of_order_not_a_gap() -> None:
    # An OCR-garbled last heading must not report thousands of missing articles.
    text = PROCLAMATION.replace("አንቀጽ ፲፪ የሚጸናበት ጊዜ", "አንቀጽ ፼፼ የሚጸናበት ጊዜ")
    units = _units(_preview(text))
    last = units["art-100000000"]
    assert OutOfSequenceIssue() in last.issues
    gaps = [
        issue
        for unit in units.values()
        for issue in unit.issues
        if isinstance(issue, NextMissingIssue)
    ]
    assert all(issue.to_number <= 12 for issue in gaps)


def test_duplicate_distance_is_the_same_for_both_copies() -> None:
    text = PROCLAMATION.replace(
        "መርሆዎቹ እኩልነትና ፍትሕ ናቸው።\n\nአንቀጽ ፭",
        "መርሆዎቹ እኩልነት፣ ፍትሕና ነፃነት ናቸው።\n\nአንቀጽ ፭",
    )
    units = _units(_preview(text))
    first = units["art-4"].issues[0]
    second = units["art-4-2"].issues[0]
    assert isinstance(first, DuplicateNumberIssue)
    assert isinstance(second, DuplicateNumberIssue)
    assert first.differing_chars == second.differing_chars > 0


def test_header_position_skips_lines_before_the_heading() -> None:
    # A second chapter-title line ends up before the next article's heading.
    text = PROCLAMATION.replace(
        "አንቀጽ ፭ መብቶች", "ምዕራፍ ሁለት\nመብቶችና ግዴታዎች\nእና ውጤቶቻቸው\n\nአንቀጽ ፭ መብቶች"
    )
    article = _units(_preview(text))["art-5"]
    lines = article.text.split("\n")
    assert lines[article.header_start] == "አንቀጽ ፭ መብቶች"
    assert article.header_lines == 1


def test_sub_article_marks_are_not_suspect_headings() -> None:
    # "፯." at the start of a line is a sub-article mark, not article ፯'s heading.
    text = PROCLAMATION.replace("ንቀጽ ፯ ኃላፊነት", "፯. ኃላፊነት በሕግ ይወሰናል")
    issue = _units(_preview(text))["art-6"].issues[0]
    assert isinstance(issue, NextMissingIssue)
    assert issue.suspect_line is None

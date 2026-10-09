from pathlib import Path

import pytest

from onyx.file_processing.legal.ethiopian_legal_splitter import (
    LegalUnit,
    LegalUnitType,
    SplitProfile,
    detect_profile,
    geez_numeral_to_int,
    int_to_geez_numeral,
    parse_legal_number,
    split_legal_text,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = Path(__file__).parents[6] / "legal_sample"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _by_id(units: list[LegalUnit]) -> dict[str, LegalUnit]:
    return {unit.unit_id: unit for unit in units}


@pytest.mark.parametrize(
    "numeral, expected",
    [
        ("፩", 1),
        ("፲፫", 13),
        ("፻", 100),
        ("፩፻", 100),
        ("፩፻፺፬", 194),
        ("፫፻፳፫", 323),
        ("፲፱፻፺፪", 1992),
        ("፼", 10000),
    ],
)
def test_geez_numeral_to_int(numeral: str, expected: int) -> None:
    assert geez_numeral_to_int(numeral) == expected


@pytest.mark.parametrize(
    "token, expected",
    [("826", 826), ("፩ሺ፸", 1070), ("፪ሺ፲", 2010), ("ሺ", 1000), ("ሺ 121", 1121)],
)
def test_parse_legal_number(token: str, expected: int) -> None:
    assert parse_legal_number(token) == expected


def test_parse_legal_number_rejects_ethiopic_digit_as_ascii() -> None:
    # "፩".isdigit() is True in Python, but int("፩") fails: it must take the Ge'ez path.
    assert parse_legal_number("፩") == 1


def test_int_to_geez_round_trip() -> None:
    for value in range(1, 1200):
        assert geez_numeral_to_int(int_to_geez_numeral(value)) == value
    assert int_to_geez_numeral(323) == "፫፻፳፫"


def test_split_profile_parse() -> None:
    assert SplitProfile.parse("Civil-Code") == SplitProfile.CIVIL_CODE
    assert SplitProfile.parse(None) == SplitProfile.NONE
    with pytest.raises(ValueError):
        SplitProfile.parse("bogus")


def test_proclamation_split() -> None:
    text = _read("family_small.md")
    assert detect_profile(text) == SplitProfile.PROCLAMATION

    result = split_legal_text(text, SplitProfile.AUTO, source_name="family_small.md")
    assert result.profile == SplitProfile.PROCLAMATION
    ids = [unit.unit_id for unit in result.units]
    assert ids == ["front-matter", *(f"art-{n}" for n in range(1, 14))]

    units = _by_id(result.units)
    front = units["front-matter"]
    assert front.unit_type == LegalUnitType.FRONT_MATTER
    assert "መግቢያ" in front.text
    assert "አንቀጽ ፩ ልዩ ልዩ" not in front.text

    art7 = units["art-7"]
    assert art7.unit_type == LegalUnitType.PROCLAMATION_ARTICLE
    assert art7.text.startswith("አንቀጽ ፯ ዕድሜ")
    assert art7.metadata["article"] == "7"
    assert art7.metadata["chapter"] == "ምዕራፍ አንድ ስለ ጋብቻ አፈጻጸም"
    assert art7.metadata["section"].startswith("ክፍል ፪ ጋብቻ ለመፈፀም")
    assert art7.title.endswith("› አንቀጽ ፯ ዕድሜ")
    assert art7.display_name.startswith("አንቀጽ ፯ ዕድሜ — ")

    # Hierarchy headings and their titles belong to no article.
    assert "ክፍል ፪" not in units["art-5"].text
    assert "ጋብቻ ለመፈፀም መሟላት ያለባቸው ሁኔታዎች" not in units["art-5"].text


def test_proclamation_repairs_ocr_damage() -> None:
    result = split_legal_text(_read("family_small.md"), SplitProfile.PROCLAMATION)
    units = _by_id(result.units)

    # "አንቀጽ ፩ሀ" sits between articles 8 and 10, so it is article 9.
    art9 = units["art-9"]
    assert art9.metadata["article"] == "9"
    assert art9.display_name.startswith("አንቀጽ ፱ የጋብቻ ዝምድና")
    assert any("repaired" in w for w in result.warnings)

    # "አንቀጽ" and its number on separate lines.
    assert units["art-10"].text.startswith("አንቀጽ\n፲ በሕግ ያልተረጋገጠ ልጅነት")

    # A cross-reference at the start of a line does not open an article.
    assert "አንቀጽ ፳ ንዑስ አንቀጽ (፫)" in units["art-11"].text
    assert "art-20" not in units


def test_proclamation_compound_chapter_number_resets_section() -> None:
    result = split_legal_text(_read("family_small.md"), SplitProfile.PROCLAMATION)
    art13 = _by_id(result.units)["art-13"]
    assert art13.metadata["chapter"] == "ምዕራፍ አሥራ አንድ ቀለብ የመስጠት ግዴታ"
    assert "section" not in art13.metadata
    assert "ምዕራፍ አሥራ አንድ" not in _by_id(result.units)["art-12"].text


def test_split_keeps_every_body_line() -> None:
    text = _read("family_small.md")
    result = split_legal_text(text, SplitProfile.PROCLAMATION)
    unit_lines = {
        line.strip() for unit in result.units for line in unit.text.splitlines()
    }
    hierarchy_lines = {
        "ምዕራፍ አንድ ስለ ጋብቻ አፈጻጸም",
        "ክፍል ፩ ጠቅላላ",
        "ክፍል ፪",
        "ጋብቻ ለመፈፀም መሟላት ያለባቸው ሁኔታዎች",
        "ምዕራፍ አሥራ አንድ",
        "ቀለብ የመስጠት ግዴታ",
    }
    for line in text.splitlines():
        line = line.strip()
        if line:
            assert line in unit_lines or line in hierarchy_lines, line


def test_cassation_split() -> None:
    text = _read("cassation_small.md")
    assert detect_profile(text) == SplitProfile.CASSATION

    result = split_legal_text(text, SplitProfile.AUTO, source_name="vol.md")
    assert result.profile == SplitProfile.CASSATION
    assert [u.unit_id for u in result.units] == [
        "case-94952",
        "case-96364",
        "case-152719",
        "case-99954",
    ]
    units = _by_id(result.units)

    first = units["case-94952"]
    assert first.unit_type == LegalUnitType.CASSATION_DECISION
    assert first.metadata["case_number"] == "94952"
    assert first.metadata["date"] == "መስከረም 30 ቀን 2007 ዓ.ም"
    # The representative after the dash is not part of the party name.
    assert first.metadata["respondent"] == "ወ/ሮ የሺ ውድዬ"
    assert first.display_name == (
        "ሰበር መ/ቁ 94952 (መስከረም 30 ቀን 2007 ዓ.ም) — ወ/ሮ ዙሪያሽ ተገኝ v. ወ/ሮ የሺ ውድዬ"
    )

    # Header-like lines inside a judgment stay in that judgment.
    second = units["case-96364"]
    assert "የሰ/መ/ቁ 12345 ላይ" in second.text
    assert "የሰ/መ/ቁ 55555" in second.text

    # A header repeated by a page break does not open a new decision.
    assert units["case-99954"].text.count("የሰ/መ/ቁ.,99954") == 2


def test_numbered_heading_proclamation() -> None:
    text = _read("amendment_proc_1070.md")
    # Too few articles to split on auto.
    assert split_legal_text(text, SplitProfile.AUTO).units == []

    result = split_legal_text(text, SplitProfile.PROCLAMATION)
    assert [u.unit_id for u in result.units] == [
        "front-matter",
        "art-1",
        "art-2",
        "art-3",
    ]
    art2 = _by_id(result.units)["art-2"]
    assert art2.text.startswith("፪. ማሻሻያ")
    # Sub-articles ("፩/ ...") stay inside their article.
    assert "፫/ የአዋጁ አንቀጽ ፩፻፺፬ (፬) ተሰርዟል።" in art2.text


def test_civil_code_split() -> None:
    text = "\n".join(
        [
            "የፍትሐ ብሔር ሕግ",
            "",
            "መጽሐፍ ፩",
            "ስለ ሰዎች",
            "አንቀጽ ፩",
            "ስለ ሰዎች በጠቅላላው",
            "ምዕራፍ ፩ ስለ ሰው ልጅ መብት",
            "ቍ ፲ ሰው መብት ያለው ስለመሆኑ",
            "የሰው ልጅ ከተወለደበት ቀን ጀምሮ መብት አለው።",
            "ቍ. ፲፩ የተፀነሰ ልጅ",
            "የተፀነሰ ልጅ በሕይወት ከተወለደ እንደተወለደ ይቆጠራል።",
            "፲፪ ስለ ስም",
            "ማንኛውም ሰው ስም አለው።",
            "ቍ ፲፫ የቤተሰብ ስም",
            "የቤተሰብ ስም ከአባት ይወሰዳል።",
        ]
    )
    result = split_legal_text(text, SplitProfile.CIVIL_CODE, source_name="civil.md")
    units = _by_id(result.units)
    assert list(units) == ["front-matter", "art-10", "art-11", "art-12", "art-13"]

    art10 = units["art-10"]
    assert art10.unit_type == LegalUnitType.CIVIL_CODE_ARTICLE
    assert art10.metadata["law"] == "የፍትሐ ብሔር ሕግ"
    assert art10.metadata["book"] == "መጽሐፍ ፩ ስለ ሰዎች"
    assert art10.metadata["part"] == "አንቀጽ ፩ ስለ ሰዎች በጠቅላላው"
    assert art10.metadata["chapter"] == "ምዕራፍ ፩ ስለ ሰው ልጅ መብት"
    assert art10.display_name.startswith("ቍ ፲ ሰው መብት ያለው ስለመሆኑ")
    # A line without ቍ is an article only when its number fits the sequence.
    assert units["art-12"].text.startswith("፲፪ ስለ ስም")


def test_single_article_stays_whole() -> None:
    result = split_legal_text(
        "መግቢያ\n\nአንቀጽ ፩ አጭር ርዕስ\n\nይህ አዋጅ ሊጠቀስ ይችላል።\n",
        SplitProfile.PROCLAMATION,
    )
    assert result.units == []
    assert result.warnings


def test_none_profile_never_splits() -> None:
    result = split_legal_text(_read("cassation_small.md"), SplitProfile.NONE)
    assert result.profile == SplitProfile.NONE
    assert result.units == []


@pytest.mark.skipif(
    not (SAMPLES / "family.md").exists(), reason="full legal samples are local-only"
)
def test_full_samples() -> None:
    family = split_legal_text(
        (SAMPLES / "family.md").read_text(encoding="utf-8"), SplitProfile.AUTO
    )
    assert family.profile == SplitProfile.PROCLAMATION
    # 327 numbered articles, the damaged "ንቀጽ ፵፪" header and the front matter.
    assert len(family.units) == 329
    assert "art-42" in _by_id(family.units)

    cassation = split_legal_text(
        (SAMPLES / "cassation 15 - 28.md").read_text(encoding="utf-8"),
        SplitProfile.AUTO,
    )
    assert cassation.profile == SplitProfile.CASSATION
    assert len(cassation.units) == 89


def test_heading_after_parenthesized_number_has_no_stray_paren() -> None:
    text = "\n".join(
        ["የሙከራ አዋጅ"]
        + [f"አንቀጽ ({n}) ርዕስ {i}\nጽሑፍ {i}።" for i, n in enumerate(["፩", "፪", "፫"])]
    )
    result = split_legal_text(text, SplitProfile.PROCLAMATION)
    assert [u.heading for u in result.units if u.number] == ["ርዕስ 0", "ርዕስ 1", "ርዕስ 2"]


def test_heading_starting_with_a_conjunction_syllable_is_kept() -> None:
    # "እናት" (mother) starts with "እና" (and) but is a heading, not a cross-reference.
    text = "\n".join(
        [
            "የሙከራ አዋጅ",
            "አንቀጽ ፩ ጠቅላላ",
            "ጽሑፍ።",
            "አንቀጽ ፪ እናት የተቀባዩን አባትነት ስላለማመንዋ",
            "ጽሑፍ።",
            "አንቀጽ ፫ ልዩ ሁኔታ",
            "ጽሑፍ።",
        ]
    )
    units = {
        u.unit_id: u for u in split_legal_text(text, SplitProfile.PROCLAMATION).units
    }
    assert units["art-2"].heading == "እናት የተቀባዩን አባትነት ስላለማመንዋ"


def test_damaged_article_word_and_ethiopic_separators_still_split() -> None:
    text = "\n".join(
        [
            "የሙከራ አዋጅ",
            "አንቀፅ ፡ ፩ ። ጠቅላላ",
            "ጽሑፍ።",
            "አንቀፅ  ፤ ፪ ። ትርጓሜ",
            "ጽሑፍ።",
            "ንቀጽ ፫ ወሰን",
            "ጽሑፍ።",
            "አንበፅ ፣ ፬ ። ተፈጻሚነት",
            "ጽሑፍ።",
            "አአንቀፅ ' ፭ ። የሚጸናበት ጊዜ",
            "ጽሑፍ።",
        ]
    )
    result = split_legal_text(text, SplitProfile.PROCLAMATION)
    assert [u.number for u in result.units if u.number] == [1, 2, 3, 4, 5]


def _decision(case_number: str, parties: list[str]) -> str:
    return "\n".join(
        [
            f"የሰበር መዝገብ ቁጥር {case_number}",
            "ጥር 10 ቀን 2010 ዓ.ም",
            "ዳኞች፡- አቶ ሀ",
            "አቶ ለ",
            *parties,
            "መዝገቡ ተመርምሮ የሚከተለው ፍርድ ተሰጥቷል።",
            "ፍርድ",
            "ጉዳዩ የሚመለከተው ...።",
        ]
    )


@pytest.mark.parametrize(
    "parties, applicant, respondent, no_respondent",
    [
        # The respondent comes after a long list of applicants.
        (
            ["አመልካቾች፡- 1ኛ. አቶ ሀ"]
            + [f"{n}ኛ. አቶ ሰው {n}" for n in range(2, 16)]
            + ["ተጠሪዎች፡- 1ኛ. አቶ ስብሃቱ ገ/መስቀል"],
            "አቶ ሀ",
            "አቶ ስብሃቱ ገ/መስቀል",
            False,
        ),
        # Both parties on one line.
        (
            ["አመልካች፡- አቶ ካሳ - ቀርበዋል ተጠሪ፡- ወ/ሮ ታደለች ዳባራ - ቀርበዋል"],
            "አቶ ካሳ",
            "ወ/ሮ ታደለች ዳባራ",
            False,
        ),
        # Older volumes: "አመልካቶች", "መልስ ሰጭ", and a glued "ከጠበቃ".
        (
            [
                "አመልካቶች፡- ወ/ሮ ሰሚራ ጀማል ከጠበቃ ሰለሞን ታደሰ ቀረቡ",
                "መልስ ሰጭ፡- የጎንደር ስጋ ፋብሪካ",
            ],
            "ወ/ሮ ሰሚራ ጀማል",
            "የጎንደር ስጋ ፋብሪካ",
            False,
        ),
        # Petitions name no respondent.
        (["አመልካች፡- ወ/ት ሞሚና ሡልጣን - ቀረቡ", "ተጠሪ፡- የለም"], "ወ/ት ሞሚና ሡልጣን", "", True),
        (["አመልካቾች፡- 1. ወ/ሮ አርሴማ ኤልያስ"], "ወ/ሮ አርሴማ ኤልያስ", "", True),
    ],
)
def test_decision_parties(
    parties: list[str], applicant: str, respondent: str, no_respondent: bool
) -> None:
    text = "\n".join(
        [
            _decision("123456", parties),
            _decision("654321", ["አመልካች፡- አቶ ሀ", "ተጠሪ፡- አቶ ለ"]),
        ]
    )
    unit = split_legal_text(text, SplitProfile.CASSATION).units[0]
    assert unit.unit_id == "case-123456"
    assert unit.metadata.get("applicant", "") == applicant
    assert unit.metadata.get("respondent", "") == respondent
    assert unit.no_respondent is no_respondent
    # The searched lines end before the judgment.
    searched = unit.text.split("\n")[: unit.details_lines]
    assert not any(line.startswith("መዝገቡ") for line in searched)

"""Convert .docx files to plain-text Markdown, one line per Word paragraph.

Streams word/document.xml, so very large OCR exports convert in seconds.
"""
import pathlib
import re
import sys
import time
import zipfile

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BLANK_RUN_RE = re.compile(r"\n{3,}")
# OCR noise between the article word and its number: "አንቀፅ  ፤ ፫ ።", "አንቀፅ ' ፵",
# "አንቀፅ  1 ፳፪". Only the prefix changes; the heading and the text stay as they are.
# The word itself may be damaged too: "አአንቀፅ", "ንቀጽ", "አንቀቀፅ", "አንበፅ".
ARTICLE_PREFIX_RE = re.compile(
    r"^\s*አ{0,2}ን[ቀበ]{1,2}(?P<z>[ጽፅ])ፐ?[\s፡፤፣።፦'\"`“”‘’;:,._\-]*(?:\d+\s+)?(?=[፩-፼]|\d)"
)
# "ቍ ፡ ፵፫ ። ..." in a file that otherwise writes "አንቀፅ ፵፫ ።".
SHORT_ARTICLE_RE = re.compile(r"^\s*ቍ[\s፡፤፣'\"`.:]*(?=[፩-፼]+\s*።)")
# A header joined to the article body: "አንቀፅ ፴፯ ። <heading> ። <body ...>".
MERGED_HEADER_RE = re.compile(
    r"^(?P<header>አንቀ[ጽፅ] [፩-፼]+\s*።\s*[^።]{1,150}።)\s*(?P<body>\S.*)$"
)
# Same, when the heading runs straight into sub-article (፩).
MERGED_SUBARTICLE_RE = re.compile(
    r"^(?P<header>አንቀ[ጽፅ] [፩-፼]+\s*።\s*[^።]{1,150}?)\s*(?P<body>\(፩\).*)$"
)
MAX_HEADER_LINE_CHARS = 200
# A header inside the previous paragraph: "... ይችላል ። ቍ ፡ ፫፻፴፫ ። <heading>".
MIDLINE_HEADER_RE = re.compile(
    r"(?<=[።፡\s])(?<!በ)(?:ቍ|አንቀ[ጽፅ])ፐ?[\s፡፤፣'\"`]*(?P<num>[፩-፼]+)\s*።"
)
LINE_HEADER_NUMBER_RE = re.compile(r"^አንቀ[ጽፅ] (?P<num>[፩-፼]+)")
GEEZ_ONES = {c: i + 1 for i, c in enumerate("፩፪፫፬፭፮፯፰፱")}
GEEZ_TENS = {c: (i + 1) * 10 for i, c in enumerate("፲፳፴፵፶፷፸፹፺")}


def geez_to_int(numeral: str) -> int | None:
    """Ge'ez numeral to int, for numbers below 10,000."""
    total = 0
    group = 0
    for char in numeral:
        if char in GEEZ_ONES:
            group += GEEZ_ONES[char]
        elif char in GEEZ_TENS:
            group += GEEZ_TENS[char]
        elif char == "፻":
            total += max(group, 1) * 100
            group = 0
        else:
            return None
    return total + group


GEEZ_ONES_BY_VALUE = {v: k for k, v in GEEZ_ONES.items()}
GEEZ_TENS_BY_VALUE = {v: k for k, v in GEEZ_TENS.items()}
# "አንቀፅ ፻ ፺፩": OCR split one numeral in two after ፻.
SPLIT_NUMERAL_RE = re.compile(r"^(?P<word>አንቀ[ጽፅ]) (?P<head>[፩-፼]*፻) (?P<tail>[፩-፼]+)")
HEADER_NUMERAL_RE = re.compile(r"^(?P<word>አንቀ[ጽፅ]) (?P<num>[፩-፼]+)")
# OCR read the Ethiopic wordspace "፡" as an apostrophe: "ይህ ' ድንጋጌ".
APOSTROPHE_WORDSPACE_RE = re.compile(r"(?<=[ሀ-፿]) ' (?=[ሀ-፿])")
MIN_APOSTROPHE_WORDSPACES = 50
MAX_RENUMBER_RUN = 3


def _below_hundred(value: int) -> str:
    return GEEZ_TENS_BY_VALUE.get(value // 10 * 10, "") + GEEZ_ONES_BY_VALUE.get(value % 10, "")


def int_to_geez(value: int, plain_hundred: bool) -> str:
    """Int below 10,000 to a Ge'ez numeral. 100-199 is "፻..." when plain_hundred."""
    hundreds, rest = divmod(value, 100)
    prefix = ""
    if hundreds == 1 and plain_hundred:
        prefix = "፻"
    elif hundreds:
        prefix = _below_hundred(hundreds) + "፻"
    return prefix + _below_hundred(rest)


# A numbered heading that lost its article word: "፰. የፌደራል ጠቅላይ ፍርድ ቤት ...".
BARE_HEADER_RE = re.compile(r"^\s*(?P<num>[፩-፼]+|\d{1,3})\s*\.\s*(?P<rest>\S.*)$")
ANY_HEADER_RE = re.compile(r"^(?P<word>አንቀ[ጽፅ]) (?P<num>[፩-፼]+|\d{1,4})")
SENTENCE_END_RE = re.compile(r"(።|፡፡|::|\.)\s*$")
MAX_BARE_HEADER_CHARS = 120


def _value(numeral: str) -> int | None:
    return int(numeral) if numeral.isascii() and numeral.isdigit() else geez_to_int(numeral)


def promote_bare_headers(lines: list[str]) -> list[str]:
    """Give a bare numbered heading its article word when the sequence proves it.

    The number must be exactly one more than the header before it and one less
    than the header after it, and the line must read as a heading, not a sentence.
    """
    headers = [i for i, line in enumerate(lines) if ANY_HEADER_RE.match(line)]
    if len(headers) < 10:
        return []
    words = [ANY_HEADER_RE.match(lines[i]).group("word") for i in headers]
    word = max(set(words), key=words.count)
    log: list[str] = []
    previous: int | None = None
    for index, line in enumerate(lines):
        header = ANY_HEADER_RE.match(line)
        if header:
            previous = _value(header.group("num"))
            continue
        bare = BARE_HEADER_RE.match(line)
        if (
            bare is None
            or previous is None
            or len(line) > MAX_BARE_HEADER_CHARS
            or SENTENCE_END_RE.search(line)
        ):
            continue
        number = _value(bare.group("num"))
        following = next((lines[j] for j in headers if j > index), None)
        following_match = ANY_HEADER_RE.match(following) if following else None
        if (
            number is not None
            and number == previous + 1
            and following_match
            and _value(following_match.group("num")) == number + 1
        ):
            lines[index] = f"{word} {line.strip()}"
            log.append(f"line {index + 1}: added the article word to '{line.strip()[:40]}'")
            previous = number
    return log


MAX_REPEAT_HEADERS = 4


def drop_repeated_blocks(lines: list[str]) -> tuple[list[str], list[str]]:
    """Drop the first copy of a scanned page that the source repeats.

    A repeat is an identical article header line that comes back within
    MAX_REPEAT_HEADERS headers. The later copy is kept: it runs on into the next
    article, while the first copy usually breaks off.
    """
    log: list[str] = []
    while True:
        headers = [i for i, line in enumerate(lines) if HEADER_NUMERAL_RE.match(line)]
        repeat = None
        for position, index in enumerate(headers):
            for earlier in headers[max(0, position - MAX_REPEAT_HEADERS) : position]:
                if lines[earlier].strip() == lines[index].strip():
                    repeat = (earlier, index)
                    break
            if repeat:
                break
        if repeat is None:
            return lines, log
        start, end = repeat
        log.append(
            f"dropped lines {start + 1}-{end}: repeated copy of '{lines[start][:40]}' and what follows"
        )
        lines = lines[:start] + lines[end:]


def correct_header_numbers(lines: list[str]) -> list[str]:
    """Fix OCR-misread article numbers that the neighbouring headers make certain.

    A run of up to three headers is renumbered only when the header after it is
    exactly the next number and the one after that confirms it. Real gaps stay.
    Returns one log line per change.
    """
    headers: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = HEADER_NUMERAL_RE.match(line)
        number = geez_to_int(match.group("num")) if match else None
        if number:
            headers.append((index, number))
    if len(headers) < 20:
        return []
    plain_hundred = sum(1 for i, _ in headers if lines[i].split(" ")[1].startswith("፻")) >= sum(
        1 for i, _ in headers if lines[i].split(" ")[1].startswith("፩፻")
    )
    numbers = [number for _, number in headers]
    log: list[str] = []
    previous: int | None = None
    for k, number in enumerate(numbers):
        if previous is not None and number != previous + 1:
            for j in range(k + 1, min(k + 1 + MAX_RENUMBER_RUN, len(numbers))):
                anchor_ok = j + 1 >= len(numbers) or numbers[j + 1] == numbers[j] + 1
                if numbers[j] == previous + (j - k + 1) and anchor_ok:
                    for t in range(k, j):
                        new = previous + (t - k + 1)
                        index = headers[t][0]
                        match = HEADER_NUMERAL_RE.match(lines[index])
                        if match is None:
                            continue
                        old = match.group("num")
                        new_text = int_to_geez(new, plain_hundred)
                        if new_text == old:
                            continue
                        lines[index] = match.group("word") + " " + new_text + lines[index][match.end():]
                        log.append(f"line {index + 1}: article {old} ({geez_to_int(old)}) -> {new_text} ({new})")
                        numbers[t] = new
                    number = numbers[k]
                    break
        if previous is None or number > previous:
            previous = number
    return log


def split_midline_headers(lines: list[str]) -> tuple[list[str], int]:
    """Start a new line at a mid-line header whose number is the next article."""
    out: list[str] = []
    last: int | None = None
    split = 0
    for line in lines:
        pending = line
        while True:
            start = LINE_HEADER_NUMBER_RE.match(pending)
            if start:
                number = geez_to_int(start.group("num"))
                if number is not None:
                    last = number
            match = None
            if last is not None:
                for candidate in MIDLINE_HEADER_RE.finditer(pending, 1):
                    if geez_to_int(candidate.group("num")) == last + 1:
                        match = candidate
                        break
            if match is None:
                out.append(pending)
                break
            out.append(pending[: match.start()].rstrip())
            pending = "አንቀፅ " + match.group("num") + " ።" + pending[match.end():]
            split += 1
    return out, split


def paragraph_text(p: etree._Element) -> str:
    parts: list[str] = []
    for el in p.iter():
        tag = el.tag
        if tag == W + "t":
            parts.append(el.text or "")
        elif tag == W + "tab":
            parts.append("\t")
        elif tag in (W + "br", W + "cr"):
            parts.append("\n")
        elif tag == W + "noBreakHyphen":
            parts.append("-")
    return "".join(parts)


def convert(path: pathlib.Path) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(path) as z, z.open("word/document.xml") as xml:
        for _, el in etree.iterparse(xml, events=("end",), tag=W + "p", huge_tree=True):
            text = paragraph_text(el)
            lines.extend(line.rstrip() for line in text.split("\n"))
            el.clear()
            parent = el.getparent()
            if parent is not None:
                while el.getprevious() is not None:
                    del parent[0]
    fixed = 0
    word_headers = sum(1 for line in lines if ARTICLE_PREFIX_RE.match(line))
    short_headers = sum(1 for line in lines if SHORT_ARTICLE_RE.match(line))
    use_short = word_headers >= 10 * max(1, short_headers)
    cleaned: list[str] = []
    for line in lines:
        clean = ARTICLE_PREFIX_RE.sub(r"አንቀ\g<z> ", line, count=1)
        if use_short and clean == line:
            clean = SHORT_ARTICLE_RE.sub("አንቀፅ ", line, count=1)
        if clean != line:
            fixed += 1
        cleaned.append(clean)
    lines, split = split_midline_headers(cleaned)
    fixed += split
    separated: list[str] = []
    for line in lines:
        merged = MERGED_HEADER_RE.match(line) or MERGED_SUBARTICLE_RE.match(line)
        if merged and len(line) > MAX_HEADER_LINE_CHARS:
            separated.extend([merged.group("header"), merged.group("body")])
            fixed += 1
        else:
            separated.append(line)
    lines = separated
    log: list[str] = []
    for index, line in enumerate(lines):
        joined = SPLIT_NUMERAL_RE.match(line)
        if joined and geez_to_int(joined.group("head") + joined.group("tail")):
            lines[index] = joined.group("word") + " " + joined.group("head") + joined.group("tail") + line[joined.end():]
            log.append(f"line {index + 1}: joined numeral '{joined.group('head')} {joined.group('tail')}'")
    log.extend(promote_bare_headers(lines))
    lines, dropped = drop_repeated_blocks(lines)
    log.extend(dropped)
    log.extend(correct_header_numbers(lines))
    wordspaces = sum(len(APOSTROPHE_WORDSPACE_RE.findall(line)) for line in lines)
    if wordspaces >= MIN_APOSTROPHE_WORDSPACES:
        lines = [APOSTROPHE_WORDSPACE_RE.sub(" ፡ ", line) for line in lines]
        log.append(f"replaced {wordspaces} apostrophe wordspaces (' ) with ፡")
    text = "\n".join(lines).strip() + "\n"
    return BLANK_RUN_RE.sub("\n\n", text), fixed, log


def main() -> None:
    out_dir = pathlib.Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    report: list[str] = ["# Conversion report", ""]
    for name in sys.argv[2:]:
        path = pathlib.Path(name)
        start = time.time()
        text, fixed, log = convert(path)
        target = out_dir / (path.stem + ".md")
        target.write_text(text, encoding="utf-8")
        print(f"{path.name}: {len(text):,} chars, {text.count(chr(10)):,} lines, {fixed} article headers cleaned, {len(log)} corrections, {time.time() - start:.1f}s")
        report.append(f"## {target.name}\n\n- {fixed} article header lines cleaned or separated")
        report.extend(f"- {entry}" for entry in log)
        report.append("")
    (out_dir.parent / "conversion_report.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()

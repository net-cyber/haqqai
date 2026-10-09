"""Remove repeated cassation decisions from converted .md files.

Run from the repo root with the backend environment:
    uv run --frozen python corpus/dedupe_decisions.py <md files...>

A decision is repeated when the same case number appears more than once and the
copies are at least MIN_SIMILARITY alike. The longest copy is kept. Changes are
appended to conversion_report.md next to the md folder.
"""

import difflib
import pathlib
import sys
from collections import defaultdict

from onyx.server.documents.file_splitting import parse_split_profile
from onyx.server.documents.file_splitting import plan_split

MIN_SIMILARITY = 0.7


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, " ".join(a.split()), " ".join(b.split()), autojunk=False).ratio()


def dedupe(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    planned = plan_split(path.name, text.encode("utf-8"), parse_split_profile("auto"))
    units = planned.result.units
    spans: list[tuple[int, int]] = []
    cursor = 0
    for unit in units:
        start = text.find(unit.text, cursor)
        if start < 0:
            raise RuntimeError(f"{path.name}: {unit.unit_id} text not found verbatim")
        spans.append((start, start + len(unit.text)))
        cursor = start + len(unit.text)
    copies: dict[str, list[int]] = defaultdict(list)
    for index, unit in enumerate(units):
        case = unit.metadata.get("case_number")
        if case:
            copies[case].append(index)
    drop: set[int] = set()
    log: list[str] = []
    for case, indices in copies.items():
        if len(indices) < 2:
            continue
        keep = max(indices, key=lambda i: len(units[i].text))
        for index in indices:
            if index == keep:
                continue
            ratio = similarity(units[keep].text, units[index].text)
            if ratio < MIN_SIMILARITY:
                log.append(f"kept both copies of case {case}: only {ratio:.0%} alike")
                continue
            drop.add(index)
            log.append(f"removed a repeated copy of case {case} ({ratio:.0%} alike, {len(units[index].text):,} chars)")
    if not drop:
        return log
    out: list[str] = []
    cursor = 0
    for index, (start, end) in enumerate(spans):
        if index in drop:
            out.append(text[cursor:start])
            cursor = end
    out.append(text[cursor:])
    cleaned = "".join(out)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    path.write_text(cleaned, encoding="utf-8")
    return log


def main() -> None:
    for name in sys.argv[1:]:
        path = pathlib.Path(name)
        log = dedupe(path)
        print(f"{path.name}: {len(log)} entries")
        for entry in log:
            print("   ", entry)
        report = path.parent.parent / "conversion_report.md"
        if log:
            with report.open("a", encoding="utf-8") as handle:
                handle.write(f"\n## {path.name}: repeated decisions\n\n" + "\n".join(f"- {e}" for e in log) + "\n")


if __name__ == "__main__":
    main()

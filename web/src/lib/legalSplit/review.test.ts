import type {
  SplitPreviewIssue,
  SplitPreviewSource,
  SplitPreviewUnit,
} from "@/lib/fileConnector";
import {
  buildOutline,
  checkKey,
  countsFor,
  defaultSelection,
  formatArticleNumber,
  matchesFilter,
  matchesQuery,
  mostSevereKind,
  nearestArticles,
} from "@/lib/legalSplit/review";

function unit(
  overrides: Partial<SplitPreviewUnit> & { unit_id: string }
): SplitPreviewUnit {
  return {
    unit_type: "proclamation_article",
    file_name: `law__${overrides.unit_id}.md`,
    label: "",
    heading: "",
    number: null,
    number_text: null,
    header_start: 0,
    header_lines: 1,
    path: [],
    case_number: null,
    date: null,
    applicant: null,
    respondent: null,
    chars: 10,
    text: "text",
    text_truncated: false,
    issues: [],
    ...overrides,
  };
}

const CHAPTER_ONE = { level: "chapter" as const, label: "ምዕራፍ አንድ" };
const CHAPTER_TWO = { level: "chapter" as const, label: "ምዕራፍ ሁለት" };
const REPAIRED: SplitPreviewIssue = {
  kind: "number_repaired",
  source_number: "፩",
  source_line: "አንቀጽ ፩ ደንብ",
};
const GAP: SplitPreviewIssue = {
  kind: "next_missing",
  from_number: 3,
  to_number: 3,
  from_text: "፫",
  to_text: "፫",
  suspect_line: null,
  suspect_text: null,
};

function source(units: SplitPreviewUnit[]): SplitPreviewSource {
  return {
    source_name: "law.md",
    size_bytes: 100,
    splittable: true,
    requested_profile: "auto",
    profile: "proclamation",
    kept_whole: null,
    law: "የሙከራ አዋጅ",
    court: null,
    volume: null,
    unit_count: units.length,
    article_count: units.length,
    units,
  };
}

const UNITS = [
  unit({ unit_id: "front-matter", unit_type: "front_matter", header_lines: 0 }),
  unit({
    unit_id: "art-1",
    number: 1,
    number_text: "፩",
    label: "አንቀጽ ፩",
    heading: "አጭር ርዕስ",
    path: [CHAPTER_ONE],
  }),
  unit({
    unit_id: "art-2",
    number: 2,
    number_text: "፪",
    label: "አንቀጽ ፪",
    heading: "ትርጓሜ",
    path: [CHAPTER_ONE],
    issues: [GAP],
  }),
  unit({
    unit_id: "art-109",
    number: 109,
    number_text: "፩፻፱",
    label: "አንቀጽ ፩፻፱",
    heading: "ደንብ",
    path: [CHAPTER_TWO],
    issues: [REPAIRED],
  }),
];

describe("matchesQuery", () => {
  test("digits match the article number by prefix", () => {
    const article = UNITS[3]!;
    expect(matchesQuery(article, "109")).toBe(true);
    expect(matchesQuery(article, "10")).toBe(true);
    expect(matchesQuery(article, "2")).toBe(false);
  });

  test("a Ge'ez numeral matches exactly", () => {
    expect(matchesQuery(UNITS[3]!, "፩፻፱")).toBe(true);
    expect(matchesQuery(UNITS[3]!, "፩")).toBe(false);
  });

  test("text matches the heading", () => {
    expect(matchesQuery(UNITS[2]!, "ትርጓ")).toBe(true);
    expect(matchesQuery(UNITS[2]!, "ደንብ")).toBe(false);
  });
});

describe("filters and counts", () => {
  test("to_check keeps flagged units, kind filters match their kind", () => {
    expect(matchesFilter(UNITS[1]!, "to_check")).toBe(false);
    expect(matchesFilter(UNITS[2]!, "to_check")).toBe(true);
    expect(matchesFilter(UNITS[3]!, "number_repaired")).toBe(true);
    expect(matchesFilter(UNITS[3]!, "next_missing")).toBe(false);
  });

  test("checked units stop counting as to check", () => {
    const src = source(UNITS);
    const checked = new Set([checkKey("law.md", UNITS[3]!)]);
    const counts = countsFor(src, checked);
    expect(counts).toMatchObject({
      all: 4,
      flagged: 2,
      checked: 1,
      toCheck: 1,
    });
    expect(counts.byKind.number_repaired).toBe(1);
    expect(counts.byKind.next_missing).toBe(1);
  });

  test("a check mark stops applying when the unit's issues change", () => {
    const before = checkKey("law.md", UNITS[3]!);
    const after = checkKey("law.md", { ...UNITS[3]!, issues: [REPAIRED, GAP] });
    expect(before).not.toBe(after);
  });

  test("the most severe issue wins", () => {
    expect(mostSevereKind([REPAIRED, GAP])).toBe("next_missing");
    expect(mostSevereKind([])).toBeNull();
  });
});

describe("buildOutline", () => {
  test("groups by chapter and shows gaps after the unit", () => {
    const { entries, visibleUnitIds } = buildOutline(source(UNITS), {
      filter: "all",
      query: "",
      checked: new Set(),
      expanded: new Set([CHAPTER_ONE.label, CHAPTER_TWO.label]),
    });
    expect(visibleUnitIds).toEqual([
      "front-matter",
      "art-1",
      "art-2",
      "art-109",
    ]);
    expect(
      entries.map((entry) =>
        entry.type === "unit" ? entry.unit.unit_id : entry.type
      )
    ).toEqual([
      "front-matter",
      "group",
      "art-1",
      "art-2",
      "gap",
      "group",
      "art-109",
    ]);
  });

  test("a closed group hides its rows but keeps them navigable", () => {
    const { entries, visibleUnitIds } = buildOutline(source(UNITS), {
      filter: "all",
      query: "",
      checked: new Set(),
      expanded: new Set([CHAPTER_TWO.label]),
    });
    expect(visibleUnitIds).toContain("art-1");
    expect(
      entries.some(
        (entry) => entry.type === "unit" && entry.unit.unit_id === "art-1"
      )
    ).toBe(false);
  });

  test("a search opens every group with a match", () => {
    const { entries, visibleUnitIds } = buildOutline(source(UNITS), {
      filter: "all",
      query: "109",
      checked: new Set(),
      expanded: new Set(),
    });
    expect(visibleUnitIds).toEqual(["art-109"]);
    expect(entries.map((entry) => entry.type)).toEqual(["group", "unit"]);
    // A narrowed list cannot collapse a group, so its header is not a toggle.
    expect(
      entries.every((entry) => entry.type !== "group" || !entry.collapsible)
    ).toBe(true);
  });

  test("groups are toggles only when nothing narrows the list", () => {
    const { entries } = buildOutline(source(UNITS), {
      filter: "all",
      query: "",
      checked: new Set(),
      expanded: new Set(),
    });
    const groups = entries.filter((entry) => entry.type === "group");
    expect(groups.length).toBeGreaterThan(0);
    expect(groups.every((entry) => entry.collapsible && !entry.open)).toBe(
      true
    );
  });
});

describe("selection and numbers", () => {
  test("the review starts on the first unit left to check", () => {
    expect(defaultSelection(source(UNITS), new Set())).toBe("art-2");
    const checked = new Set(UNITS.map((u) => checkKey("law.md", u)));
    expect(defaultSelection(source(UNITS), checked)).toBe("art-1");
  });

  test("nearest articles skip the front matter", () => {
    const { previous, next } = nearestArticles(UNITS, 1);
    expect(previous).toBeNull();
    expect(next?.unit_id).toBe("art-2");
  });

  test("article numbers show both numeral systems", () => {
    expect(formatArticleNumber("፶፱", 59)).toBe("፶፱ (59)");
    expect(formatArticleNumber("59", 59)).toBe("59");
    expect(formatArticleNumber(null, null)).toBe("");
  });
});

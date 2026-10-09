/**
 * Pure helpers for the split review: filtering, search, outline building and
 * counts. No React here, so the logic is unit-tested on its own.
 */
import type {
  SplitIssueKind,
  SplitPreviewIssue,
  SplitPreviewSource,
  SplitPreviewUnit,
} from "@/lib/fileConnector";
import type {
  OutlineEntry,
  OutlineResult,
  ReviewFilter,
  SplitReviewCounts,
} from "@/lib/legalSplit/types";

/** Most severe first. Red kinds may mean a wrong split; amber kinds were handled. */
export const ISSUE_SEVERITY: SplitIssueKind[] = [
  "out_of_sequence",
  "duplicate_number",
  "next_missing",
  "number_repaired",
  "missing_fields",
];

const GEEZ_NUMERAL_RE = /^[፩-፼]+$/;
const ASCII_DIGITS_RE = /^\d+$/;

/** Groups stay open by default up to this many units. */
export const OPEN_GROUPS_UNIT_LIMIT = 500;

export function isGeezNumeral(value: string): boolean {
  return GEEZ_NUMERAL_RE.test(value);
}

export function isDecision(unit: SplitPreviewUnit): boolean {
  return unit.unit_type === "cassation_decision";
}

export function isFlagged(unit: SplitPreviewUnit): boolean {
  return unit.issues.length > 0;
}

/**
 * Key of a "checked" mark. It includes the issue kinds, so a mark stops
 * applying when a new review finds different issues for the unit.
 */
export function checkKey(sourceName: string, unit: SplitPreviewUnit): string {
  const kinds = unit.issues.map((issue) => issue.kind).sort();
  return `${sourceName}/${unit.unit_id}/${kinds.join(",")}`;
}

export function sortedIssues(issues: SplitPreviewIssue[]): SplitPreviewIssue[] {
  return [...issues].sort(
    (a, b) => ISSUE_SEVERITY.indexOf(a.kind) - ISSUE_SEVERITY.indexOf(b.kind)
  );
}

export function mostSevereKind(
  issues: SplitPreviewIssue[]
): SplitIssueKind | null {
  const sorted = sortedIssues(issues);
  const first = sorted[0];
  return first ? first.kind : null;
}

export function matchesFilter(
  unit: SplitPreviewUnit,
  filter: ReviewFilter
): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "to_check") {
    // Checked units stay in the list, so rows do not jump while reviewing.
    return isFlagged(unit);
  }
  return unit.issues.some((issue) => issue.kind === filter);
}

/**
 * Digits match the article number by prefix ("10" finds 109) or the case
 * number; a Ge'ez numeral matches exactly; other text matches label, heading,
 * parties, case number and date.
 */
export function matchesQuery(unit: SplitPreviewUnit, query: string): boolean {
  const trimmed = query.trim();
  if (!trimmed) {
    return true;
  }
  if (ASCII_DIGITS_RE.test(trimmed)) {
    const number = unit.number === null ? "" : String(unit.number);
    return (
      number.startsWith(trimmed) || (unit.case_number ?? "").includes(trimmed)
    );
  }
  if (isGeezNumeral(trimmed)) {
    return unit.number_text === trimmed;
  }
  const needle = trimmed.toLowerCase();
  return [
    unit.label,
    unit.heading,
    unit.applicant,
    unit.respondent,
    unit.case_number,
    unit.date,
  ].some((value) => (value ?? "").toLowerCase().includes(needle));
}

/** The chapter a unit belongs to, or the book or part when there is no chapter. */
export function groupKeyOf(unit: SplitPreviewUnit): string | null {
  const chapter = unit.path.find((crumb) => crumb.level === "chapter");
  if (chapter) {
    return chapter.label;
  }
  const upper = unit.path.filter(
    (crumb) => crumb.level === "book" || crumb.level === "part"
  );
  const last = upper[upper.length - 1];
  return last ? last.label : null;
}

export function countsFor(
  source: SplitPreviewSource,
  checked: ReadonlySet<string>
): SplitReviewCounts {
  const byKind = {
    number_repaired: 0,
    out_of_sequence: 0,
    duplicate_number: 0,
    next_missing: 0,
    missing_fields: 0,
  } satisfies Record<SplitIssueKind, number>;
  let flagged = 0;
  let checkedCount = 0;
  for (const unit of source.units) {
    if (!isFlagged(unit)) {
      continue;
    }
    flagged += 1;
    if (checked.has(checkKey(source.source_name, unit))) {
      checkedCount += 1;
    }
    for (const kind of new Set(unit.issues.map((issue) => issue.kind))) {
      byKind[kind] += 1;
    }
  }
  return {
    all: source.units.length,
    toCheck: flagged - checkedCount,
    flagged,
    checked: checkedCount,
    byKind,
  };
}

interface OutlineOptions {
  filter: ReviewFilter;
  query: string;
  checked: ReadonlySet<string>;
  expanded: ReadonlySet<string>;
}

/** Build the list rows: chapter groups, section labels, units and gaps. */
export function buildOutline(
  source: SplitPreviewSource,
  { filter, query, checked, expanded }: OutlineOptions
): OutlineResult {
  const searching = query.trim().length > 0;
  const isVisible = (unit: SplitPreviewUnit) =>
    searching ? matchesQuery(unit, query) : matchesFilter(unit, filter);
  // While a filter or search narrows the list, every group with a match opens.
  const narrowed = searching || filter !== "all";
  const showGaps =
    !searching &&
    (filter === "all" || filter === "to_check" || filter === "next_missing");

  const groupOf = new Map<string, string | null>();
  const groupStats = new Map<string, { count: number; toCheck: number }>();
  for (const unit of source.units) {
    const key = groupKeyOf(unit);
    groupOf.set(unit.unit_id, key);
    if (key === null) {
      continue;
    }
    const stats = groupStats.get(key) ?? { count: 0, toCheck: 0 };
    if (isVisible(unit)) {
      stats.count += 1;
    }
    if (isFlagged(unit) && !checked.has(checkKey(source.source_name, unit))) {
      stats.toCheck += 1;
    }
    groupStats.set(key, stats);
  }

  const entries: OutlineEntry[] = [];
  const visibleUnitIds: string[] = [];
  let currentGroup: string | null = null;
  let groupOpen = true;
  const lastCrumb = new Map<string, string>();

  for (const unit of source.units) {
    if (!isVisible(unit)) {
      continue;
    }
    visibleUnitIds.push(unit.unit_id);
    const key = groupOf.get(unit.unit_id) ?? null;

    if (key !== currentGroup) {
      currentGroup = key;
      lastCrumb.clear();
      if (key !== null) {
        const stats = groupStats.get(key) ?? { count: 0, toCheck: 0 };
        groupOpen = narrowed || expanded.has(key);
        const upper = unit.path.filter(
          (crumb) => crumb.level === "book" || crumb.level === "part"
        );
        for (const crumb of upper) {
          if (crumb.label === key) {
            continue;
          }
          entries.push({
            type: "crumb",
            key: `${key}/${crumb.level}/${crumb.label}`,
            level: crumb.level,
            label: crumb.label,
          });
        }
        entries.push({
          type: "group",
          key,
          label: key,
          count: stats.count,
          toCheck: stats.toCheck,
          open: groupOpen,
          collapsible: !narrowed,
        });
      } else {
        groupOpen = true;
      }
    }
    if (!groupOpen) {
      continue;
    }

    for (const crumb of unit.path) {
      if (crumb.level !== "section" && crumb.level !== "subsection") {
        continue;
      }
      if (lastCrumb.get(crumb.level) === crumb.label) {
        continue;
      }
      lastCrumb.set(crumb.level, crumb.label);
      if (crumb.level === "section") {
        lastCrumb.delete("subsection");
      }
      entries.push({
        type: "crumb",
        key: `${key ?? ""}/${crumb.level}/${crumb.label}/${unit.unit_id}`,
        level: crumb.level,
        label: crumb.label,
      });
    }

    entries.push({ type: "unit", unit });

    if (showGaps) {
      for (const issue of unit.issues) {
        if (issue.kind === "next_missing") {
          entries.push({
            type: "gap",
            key: `gap/${unit.unit_id}`,
            issue,
          });
        }
      }
    }
  }

  return { entries, visibleUnitIds };
}

/** Nearest units before and after `index` that have an article number. */
export interface NearestArticles {
  previous: SplitPreviewUnit | null;
  next: SplitPreviewUnit | null;
}

export function nearestArticles(
  units: SplitPreviewUnit[],
  index: number
): NearestArticles {
  let previous: SplitPreviewUnit | null = null;
  for (let i = index - 1; i >= 0; i -= 1) {
    const unit = units[i];
    if (unit && unit.number !== null) {
      previous = unit;
      break;
    }
  }
  let next: SplitPreviewUnit | null = null;
  for (let i = index + 1; i < units.length; i += 1) {
    const unit = units[i];
    if (unit && unit.number !== null) {
      next = unit;
      break;
    }
  }
  return { previous, next };
}

/** "፶፱ (59)", or just "59" when the source uses Arabic digits. */
export function formatArticleNumber(
  numberText: string | null,
  number: number | null
): string {
  if (number === null) {
    return numberText ?? "";
  }
  if (!numberText || numberText === String(number)) {
    return String(number);
  }
  return `${numberText} (${number})`;
}

function nonEmptyLines(text: string): string[] {
  return text.split("\n").filter((line) => line.trim().length > 0);
}

export function lastLines(text: string, count: number): string[] {
  return nonEmptyLines(text).slice(-count);
}

export function firstLines(text: string, count: number): string[] {
  return nonEmptyLines(text).slice(0, count);
}

/** Files a source creates: one per unit, or the whole file when it is not split. */
export function sourceFileCount(source: SplitPreviewSource): number {
  return source.units.length > 0 ? source.units.length : 1;
}

/** Where the review starts: the first unit left to check, else the first article. */
export function defaultSelection(
  source: SplitPreviewSource,
  checked: ReadonlySet<string>
): string | null {
  const firstToCheck = source.units.find(
    (unit) =>
      isFlagged(unit) && !checked.has(checkKey(source.source_name, unit))
  );
  if (firstToCheck) {
    return firstToCheck.unit_id;
  }
  const firstReal = source.units.find(
    (unit) => unit.unit_type !== "front_matter"
  );
  const first = firstReal ?? source.units[0];
  return first ? first.unit_id : null;
}

/** Groups that start open: all of them for normal sizes, else only one. */
export function initialExpanded(
  source: SplitPreviewSource,
  selectedUnitId: string | null
): Set<string> {
  const keys = new Set<string>();
  if (source.units.length <= OPEN_GROUPS_UNIT_LIMIT) {
    for (const unit of source.units) {
      const key = groupKeyOf(unit);
      if (key !== null) {
        keys.add(key);
      }
    }
    return keys;
  }
  const selected = source.units.find((unit) => unit.unit_id === selectedUnitId);
  const key = selected ? groupKeyOf(selected) : null;
  if (key !== null) {
    keys.add(key);
  }
  return keys;
}

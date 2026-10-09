import {
  useCallback,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import useSWR, { type SWRResponse } from "swr";
import { useTranslations } from "next-intl";
import type { SelectOption } from "@opal/components";
import { toast } from "@opal/layouts";
import {
  previewFileSplit,
  type SplitPreviewResponse,
  type SplitPreviewSource,
  type SplitPreviewUnit,
  type SplitProfile,
  type SplitSummary,
} from "@/lib/fileConnector";
import {
  buildOutline,
  checkKey,
  countsFor,
  defaultSelection,
  groupKeyOf,
  initialExpanded,
  isFlagged,
  matchesFilter,
  matchesQuery,
} from "@/lib/legalSplit/review";
import type {
  OutlineResult,
  ReviewFilter,
  SplitReviewCounts,
} from "@/lib/legalSplit/types";

interface SplitProfileEntry {
  label: string;
  description: string;
}

interface SplitProfileLabels {
  options: SelectOption[];
  /** Translated label for a profile name returned by the backend. */
  labelFor: (profile: string) => string;
}

/** Translated choices for the File connector's legal split profile. */
export function useSplitProfileOptions(): SplitProfileLabels {
  const t = useTranslations("admin.legalSplit.profiles");

  return useMemo(() => {
    const entries = {
      none: { label: t("none.label"), description: t("none.description") },
      auto: { label: t("auto.label"), description: t("auto.description") },
      proclamation: {
        label: t("proclamation.label"),
        description: t("proclamation.description"),
      },
      civil_code: {
        label: t("civilCode.label"),
        description: t("civilCode.description"),
      },
      cassation: {
        label: t("cassation.label"),
        description: t("cassation.description"),
      },
    } satisfies Record<SplitProfile, SplitProfileEntry>;
    const options: SelectOption[] = Object.entries(entries).map(
      ([value, entry]) => ({ value, ...entry })
    );
    function labelFor(profile: string): string {
      const entry = options.find((option) => option.value === profile);
      return entry ? entry.label : profile;
    }
    return { options, labelFor };
  }, [t]);
}

/** Toast what an upload with a split profile produced. */
export function useSplitSummaryToast(): (
  summary: SplitSummary[] | null | undefined
) => void {
  const t = useTranslations("admin.legalSplit");

  return useCallback(
    (summary: SplitSummary[] | null | undefined) => {
      if (!summary || summary.length === 0) {
        return;
      }
      const split = summary.filter((source) => source.unit_count > 0);
      if (split.length > 0) {
        const files = split.reduce(
          (total, source) => total + source.unit_count,
          0
        );
        toast.success(t("createdToast", { files, sources: split.length }));
      }
      summary
        .filter((source) => source.unit_count === 0)
        .forEach((source) =>
          toast.warning(t("keptWholeToast", { source: source.source_name }))
        );
    },
    [t]
  );
}

/**
 * Fetch the split review. The key holds the files' signature and the profile,
 * so a profile change inside the open review runs it again.
 */
export function useSplitPreview(
  files: File[],
  profile: SplitProfile,
  signature: string,
  enabled: boolean
): SWRResponse<SplitPreviewResponse, Error> {
  return useSWR<SplitPreviewResponse, Error>(
    enabled ? ["legal-split-preview", signature, profile] : null,
    () => previewFileSplit(files, profile),
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: false,
    }
  );
}

function isTypingTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  );
}

/** A row to scroll into view once it renders, and whether to focus it. */
interface RevealRequest {
  unitId: string;
  focus: boolean;
}

export interface SplitReviewState {
  filter: ReviewFilter;
  setFilter: (filter: ReviewFilter) => void;
  query: string;
  setQuery: (query: string) => void;
  submitQuery: () => void;
  outline: OutlineResult;
  counts: SplitReviewCounts;
  selectedUnit: SplitPreviewUnit | null;
  selectedIndex: number;
  position: { index: number; total: number };
  previousUnit: SplitPreviewUnit | null;
  nextUnit: SplitPreviewUnit | null;
  /** Stable: safe to pass to memoized rows. */
  select: (unitId: string) => void;
  openUnit: (unitId: string) => void;
  showLine: (unitId: string, line: number) => void;
  toggleGroup: (groupKey: string) => void;
  move: (delta: number) => void;
  isChecked: (unit: SplitPreviewUnit) => boolean;
  /** Toggle the mark on the selected unit. */
  toggleChecked: () => void;
  /**
   * Toggle the mark on `unitId`. After marking, select the next unit left to
   * check. Stable: safe to pass to memoized rows.
   */
  toggleCheckedAndAdvance: (unitId: string) => void;
  bulk: { count: number; onMarkAll: () => void } | null;
  searchRef: RefObject<HTMLInputElement | null>;
  /** Stable: safe to pass to memoized rows. */
  rowRef: (unitId: string, element: HTMLElement | null) => void;
  /** Scroll the selected row into view, for example when its tab opens. */
  revealSelected: () => void;
  /** Document listener while the review is active: arrows or j/k move, / searches. */
  onKeyDown: (event: KeyboardEvent) => void;
}

/** Values that stable callbacks read at call time. */
interface LatestValues {
  checked: ReadonlySet<string>;
  visibleIds: string[];
  selectedUnitId: string | null;
  onCheckedChange: (keys: string[], value: boolean) => void;
}

/** Review state of one source: filter, search, selection, groups and marks. */
export function useSplitReviewState(
  source: SplitPreviewSource,
  checked: ReadonlySet<string>,
  onCheckedChange: (keys: string[], value: boolean) => void
): SplitReviewState {
  const unitsById = useMemo(
    () => new Map(source.units.map((unit) => [unit.unit_id, unit])),
    [source]
  );
  const groupOf = useMemo(
    () => new Map(source.units.map((unit) => [unit.unit_id, groupKeyOf(unit)])),
    [source]
  );
  const counts = useMemo(() => countsFor(source, checked), [source, checked]);

  const [initial] = useState(() => {
    const selected = defaultSelection(source, checked);
    const filter: ReviewFilter =
      countsFor(source, checked).toCheck > 0 ? "to_check" : "all";
    return {
      selected,
      filter,
      expanded: initialExpanded(source, selected),
      reveal: selected === null ? null : { unitId: selected, focus: false },
    };
  });
  const [filter, setFilterState] = useState<ReviewFilter>(initial.filter);
  const [query, setQuery] = useState("");
  // The input stays responsive; the outline follows the deferred query.
  const deferredQuery = useDeferredValue(query);
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(
    initial.selected
  );
  const [expanded, setExpanded] = useState<Set<string>>(initial.expanded);
  const [reveal, setReveal] = useState<RevealRequest | null>(initial.reveal);

  const outline = useMemo(
    () =>
      buildOutline(source, {
        filter,
        query: deferredQuery,
        checked,
        expanded,
      }),
    [source, filter, deferredQuery, checked, expanded]
  );
  const visibleIds = outline.visibleUnitIds;

  const rowRefs = useRef(new Map<string, HTMLElement>());
  const searchRef = useRef<HTMLInputElement | null>(null);
  const handledReveal = useRef<RevealRequest | null>(null);
  const latest = useRef<LatestValues>({
    checked,
    visibleIds,
    selectedUnitId,
    onCheckedChange,
  });
  useLayoutEffect(() => {
    latest.current = { checked, visibleIds, selectedUnitId, onCheckedChange };
  });

  const isChecked = useCallback(
    (unit: SplitPreviewUnit) => checked.has(checkKey(source.source_name, unit)),
    [checked, source.source_name]
  );

  const select = useCallback(
    (unitId: string, focus: boolean = false) => {
      const groupKey = groupOf.get(unitId) ?? null;
      if (groupKey !== null) {
        setExpanded((previous) =>
          previous.has(groupKey) ? previous : new Set(previous).add(groupKey)
        );
      }
      setSelectedUnitId(unitId);
      setReveal({ unitId, focus });
    },
    [groupOf]
  );
  const selectUnit = useCallback((unitId: string) => select(unitId), [select]);

  // Scroll a newly selected row into view once it renders, and focus it after
  // keyboard moves. Checks, group toggles and searches do not scroll the list.
  useEffect(() => {
    if (reveal === null || handledReveal.current === reveal) {
      return;
    }
    const row = rowRefs.current.get(reveal.unitId);
    if (!row) {
      return;
    }
    handledReveal.current = reveal;
    row.scrollIntoView({ block: "nearest" });
    if (reveal.focus) {
      row.focus({ preventScroll: true });
    }
  }, [reveal, outline.entries]);

  const revealSelected = useCallback(() => {
    const unitId = latest.current.selectedUnitId;
    if (unitId !== null) {
      setReveal({ unitId, focus: false });
    }
  }, []);

  const setFilter = useCallback(
    (next: ReviewFilter) => {
      setFilterState(next);
      setQuery("");
      const selected =
        selectedUnitId === null ? undefined : unitsById.get(selectedUnitId);
      if (selected && matchesFilter(selected, next)) {
        return;
      }
      const first = source.units.find((unit) => matchesFilter(unit, next));
      if (first) {
        select(first.unit_id);
      }
    },
    [select, selectedUnitId, source.units, unitsById]
  );

  const submitQuery = useCallback(() => {
    const trimmed = query.trim();
    const first = trimmed
      ? source.units.find((unit) => matchesQuery(unit, trimmed))?.unit_id
      : visibleIds[0];
    if (first) {
      select(first, true);
    }
  }, [query, select, source.units, visibleIds]);

  const toggleGroup = useCallback((groupKey: string) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  }, []);

  const selectedIndex =
    selectedUnitId === null ? -1 : visibleIds.indexOf(selectedUnitId);

  const move = useCallback(
    (delta: number) => {
      if (visibleIds.length === 0) {
        return;
      }
      const from = selectedIndex === -1 ? (delta > 0 ? -1 : 0) : selectedIndex;
      const target = Math.min(visibleIds.length - 1, Math.max(0, from + delta));
      const id = visibleIds[target];
      if (id !== undefined) {
        select(id, true);
      }
    },
    [select, selectedIndex, visibleIds]
  );

  const selectedUnit =
    selectedUnitId === null ? null : (unitsById.get(selectedUnitId) ?? null);
  const documentIndex = selectedUnit ? source.units.indexOf(selectedUnit) : -1;

  const toggleChecked = useCallback(() => {
    if (!selectedUnit || !isFlagged(selectedUnit)) {
      return;
    }
    const key = checkKey(source.source_name, selectedUnit);
    onCheckedChange([key], !checked.has(key));
  }, [checked, onCheckedChange, selectedUnit, source.source_name]);

  const sourceName = source.source_name;
  const toggleCheckedAndAdvance = useCallback(
    (unitId: string) => {
      const unit = unitsById.get(unitId);
      if (!unit) {
        return;
      }
      if (!isFlagged(unit)) {
        select(unitId);
        return;
      }
      const { checked: marks, visibleIds: ids } = latest.current;
      const key = checkKey(sourceName, unit);
      const nowChecked = !marks.has(key);
      latest.current.onCheckedChange([key], nowChecked);
      if (nowChecked) {
        const start = ids.indexOf(unitId);
        for (let step = 1; step < ids.length; step += 1) {
          const id = ids[(start + step) % ids.length];
          const next = id === undefined ? undefined : unitsById.get(id);
          if (
            next &&
            isFlagged(next) &&
            !marks.has(checkKey(sourceName, next))
          ) {
            select(next.unit_id, true);
            return;
          }
        }
      }
      select(unitId);
    },
    [select, sourceName, unitsById]
  );

  const openUnit = useCallback(
    (unitId: string) => {
      const target = unitsById.get(unitId);
      if (!target) {
        return;
      }
      if (!visibleIds.includes(unitId)) {
        setQuery("");
        setFilterState(matchesFilter(target, filter) ? filter : "all");
      }
      select(unitId, true);
    },
    [filter, select, unitsById, visibleIds]
  );

  const showLine = useCallback((unitId: string, line: number) => {
    document
      .getElementById(`split-line-${unitId}-${line}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, []);

  const bulk = useMemo(() => {
    if (deferredQuery.trim() || filter === "all" || filter === "to_check") {
      return null;
    }
    const keys = visibleIds
      .map((id) => unitsById.get(id))
      .filter((unit): unit is SplitPreviewUnit => unit !== undefined)
      .map((unit) => checkKey(sourceName, unit))
      .filter((key) => !checked.has(key));
    if (keys.length === 0) {
      return null;
    }
    return {
      count: keys.length,
      onMarkAll: () => onCheckedChange(keys, true),
    };
  }, [
    checked,
    deferredQuery,
    filter,
    onCheckedChange,
    sourceName,
    unitsById,
    visibleIds,
  ]);

  const rowRef = useCallback((unitId: string, element: HTMLElement | null) => {
    if (element) {
      rowRefs.current.set(unitId, element);
    } else {
      rowRefs.current.delete(unitId);
    }
  }, []);

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        isTypingTarget(event.target)
      ) {
        return;
      }
      if (event.key === "ArrowDown" || event.key === "j") {
        event.preventDefault();
        move(1);
      } else if (event.key === "ArrowUp" || event.key === "k") {
        event.preventDefault();
        move(-1);
      } else if (event.key === "/") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    },
    [move]
  );

  return {
    filter,
    setFilter,
    query,
    setQuery,
    submitQuery,
    outline,
    counts,
    selectedUnit,
    selectedIndex: documentIndex,
    position: {
      index: selectedIndex === -1 ? 0 : selectedIndex + 1,
      total: visibleIds.length,
    },
    previousUnit:
      documentIndex > 0 ? (source.units[documentIndex - 1] ?? null) : null,
    nextUnit:
      documentIndex >= 0 ? (source.units[documentIndex + 1] ?? null) : null,
    select: selectUnit,
    openUnit,
    showLine,
    toggleGroup,
    move,
    isChecked,
    toggleChecked,
    toggleCheckedAndAdvance,
    bulk,
    searchRef,
    rowRef,
    revealSelected,
    onKeyDown,
  };
}

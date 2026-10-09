"use client";

import { memo, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import {
  Button,
  EmptyMessageCard,
  InputTypeIn,
  LineItemButton,
  Tag,
  Text,
} from "@opal/components";
import { SvgCheckAll, SvgChevronRight, SvgFileText } from "@opal/icons";
import { cn } from "@opal/utils";
import type {
  NextMissingIssue,
  SplitPreviewSource,
  SplitPreviewUnit,
} from "@/lib/fileConnector";
import type { SplitReviewState } from "@/lib/legalSplit/hooks";
import { groupKeyOf, isDecision } from "@/lib/legalSplit/review";
import SplitStatusTag from "@/sections/legalSplit/SplitStatusTag";

/** Headings longer than this get a tooltip with the full text. */
const TOOLTIP_HEADING_CHARS = 40;

interface SplitUnitListProps {
  source: SplitPreviewSource;
  review: SplitReviewState;
}

/** The outline of a source: search, chapter groups, units and missing numbers. */
export default function SplitUnitList({ source, review }: SplitUnitListProps) {
  const t = useTranslations("admin.legalSplit.review.list");
  const { outline, query } = review;
  const decisions = source.units.some(isDecision);
  const selectedId = review.selectedUnit?.unit_id ?? null;

  return (
    <div className="flex h-96 shrink-0 flex-col border-b border-border-01 bg-background-tint-01 md:h-auto md:w-[22rem] md:border-b-0 md:border-e">
      <div className="flex flex-col gap-2 p-2">
        <InputTypeIn
          ref={review.searchRef}
          variant="internal"
          searchIcon
          clearButton
          value={query}
          placeholder={t("search")}
          onChange={(event) => review.setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              review.submitQuery();
            }
          }}
        />
        <div className="flex items-center justify-between gap-2 px-1">
          <Text font="secondary-body" color="text-03">
            {t("showing", {
              shown: outline.visibleUnitIds.length,
              total: source.units.length,
            })}
          </Text>
          {review.bulk && (
            <Button
              prominence="tertiary"
              size="sm"
              icon={SvgCheckAll}
              onClick={review.bulk.onMarkAll}
            >
              {t("markAll", { count: review.bulk.count })}
            </Button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1 pb-2">
        {outline.visibleUnitIds.length === 0 ? (
          <div className="p-2">
            <EmptyMessageCard
              sizePreset="main-ui"
              title={
                query.trim()
                  ? t("noResults.title", { query: query.trim() })
                  : t("noResults.filterTitle")
              }
              description={t("noResults.description")}
            />
          </div>
        ) : (
          outline.entries.map((entry) => {
            switch (entry.type) {
              case "group":
                if (!entry.collapsible) {
                  return (
                    <SplitGroupLabel
                      key={`group-${entry.key}`}
                      label={entry.label}
                      count={entry.count}
                      toCheck={entry.toCheck}
                    />
                  );
                }
                return (
                  <LineItemButton
                    key={`group-${entry.key}`}
                    sizePreset="main-ui"
                    variant="section"
                    rounding={2}
                    title={entry.label}
                    titleMaxLines={1}
                    aria-expanded={entry.open}
                    onClick={() => review.toggleGroup(entry.key)}
                    rightChildren={
                      <div className="flex items-center gap-1">
                        <Text font="secondary-mono" color="text-03">
                          {String(entry.count)}
                        </Text>
                        {entry.toCheck > 0 && (
                          <Tag
                            size="sm"
                            color="amber"
                            title={String(entry.toCheck)}
                          />
                        )}
                        <SvgChevronRight
                          size={14}
                          className={cn(
                            "stroke-text-03 transition-transform",
                            entry.open ? "rotate-90" : "rtl:rotate-180"
                          )}
                        />
                      </div>
                    }
                  />
                );
              case "crumb":
                return (
                  <div
                    key={entry.key}
                    className={cn(
                      "py-1",
                      entry.level === "subsection"
                        ? "ps-6"
                        : entry.level === "section"
                          ? "ps-3"
                          : "ps-1"
                    )}
                    lang="am"
                    dir="auto"
                  >
                    <Text
                      font={
                        entry.level === "subsection"
                          ? "secondary-body"
                          : "secondary-action"
                      }
                      color="text-03"
                      maxLines={1}
                    >
                      {entry.label}
                    </Text>
                  </div>
                );
              case "unit":
                return (
                  <SplitUnitRow
                    key={entry.unit.unit_id}
                    unit={entry.unit}
                    nested={!decisions && groupKeyOf(entry.unit) !== null}
                    decisionSource={decisions}
                    selected={entry.unit.unit_id === selectedId}
                    isChecked={review.isChecked(entry.unit)}
                    onSelect={review.select}
                    onSpace={review.toggleCheckedAndAdvance}
                    rowRef={review.rowRef}
                  />
                );
              case "gap":
                return <SplitGapRow key={entry.key} issue={entry.issue} />;
              default: {
                const unhandled: never = entry;
                return unhandled;
              }
            }
          })
        )}
      </div>

      <div className="border-t border-border-01 p-2">
        <Text font="figure-keystroke" color="text-03">
          {t("keys")}
        </Text>
      </div>
    </div>
  );
}

interface SplitGroupLabelProps {
  label: string;
  count: number;
  toCheck: number;
}

/** A chapter heading while a filter or search keeps every matching group open. */
function SplitGroupLabel({ label, count, toCheck }: SplitGroupLabelProps) {
  return (
    <div className="flex h-8 items-center gap-2 px-2" lang="am" dir="auto">
      <div className="min-w-0 flex-1">
        <Text font="main-ui-action" color="text-04" maxLines={1}>
          {label}
        </Text>
      </div>
      <Text font="secondary-mono" color="text-03">
        {String(count)}
      </Text>
      {toCheck > 0 && <Tag size="sm" color="amber" title={String(toCheck)} />}
    </div>
  );
}

interface SplitUnitRowProps {
  unit: SplitPreviewUnit;
  nested: boolean;
  /** True when the source holds court decisions, not articles. */
  decisionSource: boolean;
  selected: boolean;
  isChecked: boolean;
  onSelect: (unitId: string) => void;
  onSpace: (unitId: string) => void;
  rowRef: (unitId: string, element: HTMLElement | null) => void;
}

const SplitUnitRow = memo(function SplitUnitRow({
  unit,
  nested,
  decisionSource,
  selected,
  isChecked,
  onSelect,
  onSpace,
  rowRef,
}: SplitUnitRowProps) {
  const t = useTranslations("admin.legalSplit.review.list");
  const decision = isDecision(unit);
  const frontMatter = unit.unit_type === "front_matter";

  const title = frontMatter
    ? decisionSource
      ? t("frontMatterDecisions")
      : t("frontMatterArticles")
    : decision
      ? t("decisionTitle", {
          caseNumber: unit.case_number ?? unit.label,
          applicant: unit.applicant ?? t("missingValue"),
          respondent: unit.respondent ?? t("missingValue"),
        })
      : `${unit.number_text ?? ""} ${unit.heading}`.trim() || unit.label;

  const arabicNumber =
    !decision &&
    unit.number !== null &&
    unit.number_text !== String(unit.number)
      ? String(unit.number)
      : null;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === " ") {
      event.preventDefault();
      onSpace(unit.unit_id);
    }
  };

  return (
    <div className={nested ? "ps-3" : undefined} lang="am">
      <LineItemButton
        ref={(element: HTMLElement | null) => rowRef(unit.unit_id, element)}
        selectVariant="select-heavy"
        state={selected ? "selected" : "empty"}
        sizePreset="main-ui"
        variant="section"
        rounding={2}
        icon={frontMatter ? SvgFileText : undefined}
        title={title}
        titleMaxLines={1}
        description={
          decision && !frontMatter
            ? (unit.date ?? t("dateNotFound"))
            : undefined
        }
        descriptionMaxLines={1}
        tooltip={
          !decision && unit.heading.length > TOOLTIP_HEADING_CHARS
            ? unit.heading
            : undefined
        }
        aria-current={selected ? "true" : undefined}
        data-unit-id={unit.unit_id}
        onClick={() => onSelect(unit.unit_id)}
        onKeyDown={handleKeyDown}
        rightChildren={
          <div className="flex items-center gap-1">
            {arabicNumber && (
              <Text font="secondary-mono" color="text-03">
                {arabicNumber}
              </Text>
            )}
            <SplitStatusTag issues={unit.issues} isChecked={isChecked} />
          </div>
        }
      />
    </div>
  );
});

interface SplitGapRowProps {
  issue: NextMissingIssue;
}

/** Article numbers that are not in the file, shown where they should be. */
function SplitGapRow({ issue }: SplitGapRowProps) {
  const t = useTranslations("admin.legalSplit.review.list");
  return (
    <div className="my-0.5 ms-3 flex h-6 items-center border-y border-dashed border-border-02 px-2">
      <Text font="secondary-body" color="text-03" maxLines={1}>
        {issue.from_number === issue.to_number
          ? t("gapOne", {
              numberText: issue.from_text,
              number: issue.from_number,
            })
          : t("gapRange", {
              fromText: issue.from_text,
              toText: issue.to_text,
              from: issue.from_number,
              to: issue.to_number,
            })}
      </Text>
    </div>
  );
}

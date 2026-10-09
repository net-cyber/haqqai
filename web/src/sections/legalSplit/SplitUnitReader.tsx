"use client";

import { useTranslations } from "next-intl";
import { Button, Card, MessageCard, Text, Tooltip } from "@opal/components";
import {
  SvgCheck,
  SvgCheckCircle,
  SvgChevronDown,
  SvgChevronUp,
} from "@opal/icons";
import { cn, richNodes } from "@opal/utils";
import type {
  SplitPathLevel,
  SplitPreviewSource,
  SplitPreviewUnit,
} from "@/lib/fileConnector";
import {
  firstLines,
  isDecision,
  isFlagged,
  lastLines,
  nearestArticles,
  sortedIssues,
} from "@/lib/legalSplit/review";
import SplitIssueCard from "@/sections/legalSplit/SplitIssueCard";

const BOUNDARY_LINES = 2;
// Decision details are read from this many lines; matches the backend.
const DECISION_HEADER_LINES = 15;
// Keeps empty lines at full height.
const NO_BREAK_SPACE = "\u00a0";

interface SplitUnitReaderProps {
  source: SplitPreviewSource;
  unit: SplitPreviewUnit;
  /** Index of `unit` in `source.units`. */
  documentIndex: number;
  previousUnit: SplitPreviewUnit | null;
  nextUnit: SplitPreviewUnit | null;
  position: { index: number; total: number };
  isChecked: boolean;
  unitById: (unitId: string) => SplitPreviewUnit | undefined;
  onToggleChecked: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onOpenUnit: (unitId: string) => void;
  onShowLine: (line: number) => void;
}

/** One unit exactly as it will be stored, with the evidence for its issues. */
export default function SplitUnitReader({
  source,
  unit,
  documentIndex,
  previousUnit,
  nextUnit,
  position,
  isChecked,
  unitById,
  onToggleChecked,
  onPrevious,
  onNext,
  onOpenUnit,
  onShowLine,
}: SplitUnitReaderProps) {
  const t = useTranslations("admin.legalSplit.review.reader");
  const decision = isDecision(unit);
  const frontMatter = unit.unit_type === "front_matter";
  const { previous: previousArticle, next: nextArticle } = nearestArticles(
    source.units,
    documentIndex
  );
  const issues = sortedIssues(unit.issues);
  const breadcrumb = decision
    ? (source.court ?? source.source_name)
    : [source.law, ...unit.path.map((crumb) => crumb.label)]
        .filter((part): part is string => Boolean(part))
        .join(" › ");

  return (
    <div className="flex min-h-[32rem] min-w-0 flex-1 flex-col bg-background-tint-00 md:min-h-0">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border-01 px-4">
        <div className="min-w-0 flex-1 overflow-hidden" title={breadcrumb}>
          <Text
            font="secondary-body"
            color="text-03"
            maxLines={1}
            lang="am"
            dir="auto"
          >
            {breadcrumb}
          </Text>
        </div>
        <Text font="secondary-mono" color="text-03">
          {t("position", { index: position.index, total: position.total })}
        </Text>
        <Button
          prominence="tertiary"
          size="sm"
          icon={SvgChevronUp}
          tooltip={t("previous")}
          onClick={onPrevious}
        />
        <Button
          prominence="tertiary"
          size="sm"
          icon={SvgChevronDown}
          tooltip={t("next")}
          onClick={onNext}
        />
        {isFlagged(unit) &&
          (isChecked ? (
            <Button
              prominence="tertiary"
              size="sm"
              icon={SvgCheckCircle}
              tooltip={t("undo")}
              onClick={onToggleChecked}
            >
              {t("checked")}
            </Button>
          ) : (
            <Button
              prominence="secondary"
              size="sm"
              icon={SvgCheck}
              onClick={onToggleChecked}
            >
              {t("markChecked")}
            </Button>
          ))}
      </div>

      <div
        key={unit.unit_id}
        className="min-h-0 flex-1 overflow-y-auto px-6 py-5"
      >
        <div className="flex max-w-[44rem] flex-col gap-4">
          <div className="flex flex-col gap-1">
            <Text as="h2" font="heading-h2" color="text-05" lang="am">
              {frontMatter ? t("frontMatterTitle") : unit.label}
            </Text>
            <Text font="secondary-mono" color="text-03">
              {decision && unit.date
                ? t("decisionMeta", { date: unit.date, chars: unit.chars })
                : unit.number !== null
                  ? t("articleMeta", { number: unit.number, chars: unit.chars })
                  : t("chars", { chars: unit.chars })}
            </Text>
            {!decision && unit.heading && (
              <Text
                as="h3"
                font="heading-h3"
                color="text-05"
                lang="am"
                dir="auto"
              >
                {unit.heading}
              </Text>
            )}
          </div>

          {issues.map((issue) => (
            <SplitIssueCard
              key={issue.kind}
              issue={issue}
              unit={unit}
              previousArticle={previousArticle}
              nextArticle={nextArticle}
              unitById={unitById}
              onOpenUnit={onOpenUnit}
              onShowLine={onShowLine}
            />
          ))}
          {issues.length > 0 && (
            <Text as="p" font="secondary-body" color="text-03">
              {t("fixHint", { fileName: unit.file_name })}
            </Text>
          )}

          {previousUnit && (
            <SplitBoundary kind="previous" unit={previousUnit} />
          )}
          <SplitUnitBody unit={unit} />
          {nextUnit && <SplitBoundary kind="next" unit={nextUnit} />}

          {unit.text_truncated && (
            <MessageCard
              variant="info"
              padding={1}
              title={t("truncated", {
                shown: unit.text.length,
                total: unit.chars,
              })}
            />
          )}

          <SplitUnitDetails source={source} unit={unit} />
        </div>
      </div>
    </div>
  );
}

interface SplitBoundaryProps {
  kind: "previous" | "next";
  unit: SplitPreviewUnit;
}

/** The end of the file before, or the start of the file after, to check the cut. */
function SplitBoundary({ kind, unit }: SplitBoundaryProps) {
  const t = useTranslations("admin.legalSplit.review.reader");
  const lines =
    kind === "previous"
      ? lastLines(unit.text, BOUNDARY_LINES)
      : firstLines(unit.text, BOUNDARY_LINES);
  const label =
    unit.unit_type === "front_matter" ? t("frontMatterTitle") : unit.label;
  return (
    <Card color="background-tint-01" border="dashed" padding={2}>
      <div className="flex flex-col gap-1">
        <Text font="secondary-body" color="text-03">
          {kind === "previous"
            ? t("previousEnd", { label })
            : t("nextStart", { label })}
        </Text>
        <div className="flex flex-col whitespace-pre-wrap" lang="am" dir="auto">
          {lines.map((line, index) => (
            <Text key={index} as="p" font="main-content-muted" color="text-03">
              {line}
            </Text>
          ))}
        </div>
      </div>
    </Card>
  );
}

interface SplitUnitBodyProps {
  unit: SplitPreviewUnit;
}

/** The unit's text line by line, with the lines its issues refer to marked. */
function SplitUnitBody({ unit }: SplitUnitBodyProps) {
  const t = useTranslations("admin.legalSplit.review.reader");
  const lines = unit.text.split("\n");
  let repairedNumber: string | null = null;
  let outOfSequence = false;
  let suspectLine: number | null = null;
  let headerWindow = 0;
  for (const issue of unit.issues) {
    if (issue.kind === "number_repaired") {
      repairedNumber = issue.source_number;
    } else if (issue.kind === "out_of_sequence") {
      outOfSequence = true;
    } else if (issue.kind === "next_missing") {
      suspectLine = issue.suspect_line;
    } else if (issue.kind === "missing_fields") {
      headerWindow = issue.searched_lines;
    }
  }
  const headerStart = unit.header_start;
  const headerEnd = headerStart + unit.header_lines;
  const markedHeaderLine =
    repairedNumber === null
      ? -1
      : lines.findIndex(
          (line, index) =>
            index >= headerStart &&
            index < headerStart + Math.max(1, unit.header_lines) &&
            line.includes(repairedNumber ?? "")
        );

  const renderLine = (line: string, index: number) => {
    const isHeader = index >= headerStart && index < headerEnd;
    const highlighted =
      (outOfSequence && isHeader) ||
      index === suspectLine ||
      (repairedNumber !== null &&
        markedHeaderLine === -1 &&
        index === headerStart);
    const at =
      repairedNumber !== null && index === markedHeaderLine
        ? line.indexOf(repairedNumber)
        : -1;
    const children =
      repairedNumber !== null && at >= 0
        ? richNodes(
            <>
              {line.slice(0, at)}
              <mark className="rounded-04 bg-highlight-match px-0.5 text-inherit">
                {repairedNumber}
              </mark>
              {line.slice(at + repairedNumber.length)}
            </>
          )
        : line.length > 0
          ? line
          : NO_BREAK_SPACE;
    return (
      <div
        key={index}
        id={`split-line-${unit.unit_id}-${index}`}
        className={cn(
          "rounded-04 px-1",
          highlighted &&
            (outOfSequence && isHeader
              ? "bg-status-error-01"
              : "bg-highlight-match")
        )}
      >
        <Text
          as="p"
          font={isHeader ? "main-content-emphasis" : "main-content-body"}
          color="text-05"
        >
          {children}
        </Text>
      </div>
    );
  };

  const windowLines = headerWindow > 0 ? lines.slice(0, headerWindow) : [];
  const restLines = headerWindow > 0 ? lines.slice(headerWindow) : lines;

  return (
    <div className="flex flex-col whitespace-pre-wrap" lang="am" dir="auto">
      {windowLines.length > 0 && (
        <div className="flex flex-col gap-1 rounded-08 bg-background-tint-01 p-2">
          <Text font="secondary-body" color="text-03">
            {t("headerWindow")}
          </Text>
          <div className="flex flex-col">
            {windowLines.map((line, index) => renderLine(line, index))}
          </div>
        </div>
      )}
      {restLines.map((line, index) =>
        renderLine(line, index + windowLines.length)
      )}
    </div>
  );
}

interface SplitUnitDetailsProps {
  source: SplitPreviewSource;
  unit: SplitPreviewUnit;
}

/** Where the unit is stored and what the splitter read from its header. */
function SplitUnitDetails({ source, unit }: SplitUnitDetailsProps) {
  const t = useTranslations("admin.legalSplit.review.field");
  const tReader = useTranslations("admin.legalSplit.review.reader");
  const missingFields = unit.issues.find(
    (issue) => issue.kind === "missing_fields"
  );
  const searchedLines =
    missingFields?.kind === "missing_fields"
      ? missingFields.searched_lines
      : DECISION_HEADER_LINES;
  const levelLabel = (level: SplitPathLevel): string => {
    switch (level) {
      case "book":
        return t("book");
      case "part":
        return t("part");
      case "chapter":
        return t("chapter");
      case "section":
        return t("section");
      case "subsection":
        return t("subsection");
      default: {
        const unhandled: never = level;
        return unhandled;
      }
    }
  };

  const rows: { key: string; label: string; value: string | null }[] = [
    { key: "storedAs", label: t("storedAs"), value: unit.file_name },
    {
      key: "size",
      label: t("size"),
      value: tReader("chars", { chars: unit.chars }),
    },
  ];
  if (isDecision(unit)) {
    rows.push(
      { key: "caseNumber", label: t("caseNumber"), value: unit.case_number },
      { key: "date", label: t("date"), value: unit.date },
      { key: "applicant", label: t("applicant"), value: unit.applicant },
      { key: "respondent", label: t("respondent"), value: unit.respondent },
      { key: "court", label: t("court"), value: source.court },
      { key: "volume", label: t("volume"), value: source.volume }
    );
  } else {
    unit.path.forEach((crumb, index) =>
      rows.push({
        key: `path-${index}`,
        label: levelLabel(crumb.level),
        value: crumb.label,
      })
    );
  }

  return (
    <div className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-1 border-t border-border-01 pt-4">
      {rows.map((row) => (
        <div key={row.key} className="contents">
          <Text font="secondary-body" color="text-03">
            {row.label}
          </Text>
          {row.value ? (
            <Text font="main-ui-body" color="text-04" lang="am" dir="auto">
              {row.value}
            </Text>
          ) : (
            <Tooltip
              tooltip={t("notFound", { lines: searchedLines })}
              side="top"
              align="start"
            >
              <div>
                <Text font="main-ui-body" color="text-03">
                  {t("missingValue")}
                </Text>
              </div>
            </Tooltip>
          )}
        </div>
      ))}
    </div>
  );
}

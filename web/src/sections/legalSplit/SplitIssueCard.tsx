"use client";

import { useFormatter, useTranslations } from "next-intl";
import { Button, MessageCard, Text } from "@opal/components";
import type {
  SplitCaseField,
  SplitPreviewIssue,
  SplitPreviewUnit,
} from "@/lib/fileConnector";
import { formatArticleNumber } from "@/lib/legalSplit/review";

/** Up to this many differing characters, two copies count as nearly the same. */
const NEARLY_SAME_MAX_CHARS = 10;

interface SplitIssueCardProps {
  issue: SplitPreviewIssue;
  unit: SplitPreviewUnit;
  /** Nearest units with an article number, for wording the sequence. */
  previousArticle: SplitPreviewUnit | null;
  nextArticle: SplitPreviewUnit | null;
  unitById: (unitId: string) => SplitPreviewUnit | undefined;
  onOpenUnit: (unitId: string) => void;
  onShowLine: (line: number) => void;
}

function articleNumber(unit: SplitPreviewUnit | null): string | null {
  return unit ? formatArticleNumber(unit.number_text, unit.number) : null;
}

/** One issue of a unit, in plain language, with the action that helps check it. */
export default function SplitIssueCard({
  issue,
  unit,
  previousArticle,
  nextArticle,
  unitById,
  onOpenUnit,
  onShowLine,
}: SplitIssueCardProps) {
  const t = useTranslations("admin.legalSplit.review.issue");
  const tField = useTranslations("admin.legalSplit.review.field");
  const format = useFormatter();
  const previous = articleNumber(previousArticle);
  const next = articleNumber(nextArticle);
  const used = formatArticleNumber(unit.number_text, unit.number);

  switch (issue.kind) {
    case "number_repaired":
      return (
        <MessageCard
          variant="warning"
          padding={1}
          title={t("numberRepaired.title")}
          description={
            previous && next
              ? t("numberRepaired.body", {
                  source: issue.source_number,
                  previous,
                  next,
                  used,
                })
              : t("numberRepaired.bodyEdge", {
                  source: issue.source_number,
                  used,
                })
          }
        />
      );
    case "out_of_sequence":
      return (
        <MessageCard
          variant="error"
          padding={1}
          title={t("outOfSequence.title")}
          description={
            previous && next
              ? t("outOfSequence.body", { number: used, previous, next })
              : t("outOfSequence.bodyEdge")
          }
        />
      );
    case "duplicate_number": {
      const otherId = issue.other_unit_ids[0];
      const other = otherId === undefined ? undefined : unitById(otherId);
      const sameness =
        issue.differing_chars === 0
          ? t("duplicate.same")
          : issue.differing_chars <= NEARLY_SAME_MAX_CHARS
            ? t("duplicate.nearly", { count: issue.differing_chars })
            : t("duplicate.different");
      return (
        <MessageCard
          variant="error"
          padding={1}
          title={
            unit.unit_type === "cassation_decision"
              ? t("duplicate.titleCase")
              : t("duplicate.title")
          }
          description={t("duplicate.body", {
            label: unit.label,
            otherFile: other ? other.file_name : "",
          })}
          bottomChildren={
            <div className="flex flex-wrap items-center gap-2">
              <Text font="secondary-body" color="text-04">
                {sameness}
              </Text>
              {otherId !== undefined && (
                <Button
                  prominence="tertiary"
                  size="sm"
                  onClick={() => onOpenUnit(otherId)}
                >
                  {t("duplicate.openOther")}
                </Button>
              )}
            </div>
          }
        />
      );
    }
    case "next_missing": {
      const body =
        issue.from_number === issue.to_number
          ? t("nextMissing.bodyOne", {
              numberText: issue.from_text,
              number: issue.from_number,
            })
          : t("nextMissing.bodyRange", {
              fromText: issue.from_text,
              toText: issue.to_text,
              from: issue.from_number,
              to: issue.to_number,
            });
      const suspectLine = issue.suspect_line;
      return (
        <MessageCard
          variant="error"
          padding={1}
          title={t("nextMissing.title")}
          description={body}
          bottomChildren={
            suspectLine !== null ? (
              <div className="flex flex-col items-start gap-2">
                <Text
                  font="secondary-body"
                  color="text-04"
                  lang="am"
                  dir="auto"
                >
                  {t("nextMissing.suspect", {
                    line: suspectLine + 1,
                    text: issue.suspect_text ?? "",
                  })}
                </Text>
                <Button
                  prominence="tertiary"
                  size="sm"
                  onClick={() => onShowLine(suspectLine)}
                >
                  {t("nextMissing.showLine")}
                </Button>
              </div>
            ) : (
              <Text font="secondary-body" color="text-04">
                {t("nextMissing.noSuspect")}
              </Text>
            )
          }
        />
      );
    }
    case "missing_fields": {
      const names = issue.fields.map((field: SplitCaseField) => {
        switch (field) {
          case "date":
            return tField("nameDate");
          case "applicant":
            return tField("nameApplicant");
          case "respondent":
            return tField("nameRespondent");
          default: {
            const unhandled: never = field;
            return unhandled;
          }
        }
      });
      return (
        <MessageCard
          variant="warning"
          padding={1}
          title={t("missingFields.title")}
          description={t("missingFields.body", {
            fields: format.list(names, { type: "conjunction" }),
            lines: issue.searched_lines,
          })}
        />
      );
    }
    default: {
      const unhandled: never = issue;
      return unhandled;
    }
  }
}

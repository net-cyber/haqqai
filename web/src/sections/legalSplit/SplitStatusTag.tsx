"use client";

import { useTranslations } from "next-intl";
import { Tag } from "@opal/components";
import { SvgCheck } from "@opal/icons";
import type { SplitPreviewIssue } from "@/lib/fileConnector";
import { mostSevereKind } from "@/lib/legalSplit/review";

interface SplitStatusTagProps {
  issues: SplitPreviewIssue[];
  isChecked: boolean;
}

/** The status of one unit in the review list: its most severe issue, or "Checked". */
export default function SplitStatusTag({
  issues,
  isChecked,
}: SplitStatusTagProps) {
  const t = useTranslations("admin.legalSplit.review.tag");
  if (issues.length === 0) {
    return null;
  }
  if (isChecked) {
    return <Tag size="sm" color="green" icon={SvgCheck} title={t("checked")} />;
  }
  const kind = mostSevereKind(issues);
  switch (kind) {
    case "out_of_sequence":
      return <Tag size="sm" color="red" title={t("outOfSequence")} />;
    case "duplicate_number":
      return <Tag size="sm" color="red" title={t("duplicate")} />;
    case "next_missing":
      return <Tag size="sm" color="red" title={t("nextMissing")} />;
    case "number_repaired":
      return <Tag size="sm" color="amber" title={t("numberRepaired")} />;
    case "missing_fields":
      return <Tag size="sm" color="amber" title={t("missingFields")} />;
    case null:
      return null;
    default: {
      const unhandled: never = kind;
      return unhandled;
    }
  }
}

"use client";

import { useTranslations } from "next-intl";
import { Tag, Text } from "@opal/components";
import type { SplitPreviewSource } from "@/lib/fileConnector";
import { countsFor } from "@/lib/legalSplit/review";

interface SplitSummaryRowsProps {
  sources: SplitPreviewSource[];
  checked: ReadonlySet<string>;
}

/** One line per reviewed file, shown on the form after the review closes. */
export default function SplitSummaryRows({
  sources,
  checked,
}: SplitSummaryRowsProps) {
  const t = useTranslations("admin.legalSplit.review.entry");
  return (
    <div className="flex flex-col">
      {sources.map((source) => {
        const counts = countsFor(source, checked);
        return (
          <div
            key={source.source_name}
            className="flex flex-wrap items-center gap-2 py-1"
          >
            <Text font="main-ui-body" color="text-04" maxLines={1}>
              {source.source_name}
            </Text>
            {!source.splittable ? (
              <Tag size="sm" title={t("notSplit")} />
            ) : source.units.length === 0 ? (
              <Tag size="sm" title={t("keptWhole")} />
            ) : (
              <>
                <Tag
                  size="sm"
                  title={t("files", { count: source.units.length })}
                />
                {counts.toCheck > 0 ? (
                  <Tag
                    size="sm"
                    color="amber"
                    title={t("toCheck", { count: counts.toCheck })}
                  />
                ) : (
                  <Tag size="sm" color="green" title={t("noIssues")} />
                )}
                {counts.checked > 0 && (
                  <Text font="secondary-body" color="text-03">
                    {t("checked", { count: counts.checked })}
                  </Text>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

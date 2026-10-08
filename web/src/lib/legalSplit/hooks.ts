import { useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";
import type { SelectOption } from "@opal/components";
import { toast } from "@opal/layouts";
import type { SplitProfile, SplitSummary } from "@/lib/fileConnector";

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

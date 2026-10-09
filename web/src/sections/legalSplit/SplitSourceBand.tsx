"use client";

import { useTranslations } from "next-intl";
import {
  InputSingleSelect,
  MessageCard,
  SelectButton,
  Tag,
  Text,
  Tooltip,
  type SelectOption,
} from "@opal/components";
import { SvgCheckCircle } from "@opal/icons";
import {
  isSplitProfile,
  type SplitIssueKind,
  type SplitPreviewSource,
  type SplitProfile,
} from "@/lib/fileConnector";
import { isDecision } from "@/lib/legalSplit/review";
import type { ReviewFilter, SplitReviewCounts } from "@/lib/legalSplit/types";
import { formatBytes } from "@/lib/utils";

interface SplitSourceBandProps {
  source: SplitPreviewSource;
  counts: SplitReviewCounts;
  filter: ReviewFilter;
  onFilterChange: (filter: ReviewFilter) => void;
  profile: SplitProfile;
  profileOptions: SelectOption[];
  profileLabel: (profile: string) => string;
  onProfileChange: (profile: SplitProfile) => void;
  textBudgetExceeded: boolean;
}

interface Chip {
  filter: ReviewFilter;
  label: string;
  count: number;
}

/** The source header: what the file is, how it was split, and the filters. */
export default function SplitSourceBand({
  source,
  counts,
  filter,
  onFilterChange,
  profile,
  profileOptions,
  profileLabel,
  onProfileChange,
  textBudgetExceeded,
}: SplitSourceBandProps) {
  const t = useTranslations("admin.legalSplit.review");
  const decisions = source.units.some(isDecision);
  const hasFrontMatter = source.units.some(
    (unit) => unit.unit_type === "front_matter"
  );
  const chapters = new Set(
    source.units.flatMap((unit) =>
      unit.path
        .filter((crumb) => crumb.level === "chapter")
        .map((crumb) => crumb.label)
    )
  ).size;
  const title = decisions
    ? (source.court ?? source.source_name)
    : (source.law ?? source.source_name);
  const appliedLabel =
    source.requested_profile === "auto"
      ? t("source.detected", { profile: profileLabel(source.profile) })
      : profileLabel(source.profile);

  const kindChip = (kind: SplitIssueKind, label: string): Chip => ({
    filter: kind,
    label,
    count: counts.byKind[kind],
  });
  const fixedChips: Chip[] = decisions
    ? [
        kindChip(
          "missing_fields",
          t("filter.missingFields", { count: counts.byKind.missing_fields })
        ),
      ]
    : [
        kindChip(
          "number_repaired",
          t("filter.numberRepaired", { count: counts.byKind.number_repaired })
        ),
      ];
  const checkChips: Chip[] = decisions
    ? [
        kindChip(
          "duplicate_number",
          t("filter.duplicate", { count: counts.byKind.duplicate_number })
        ),
      ]
    : [
        kindChip(
          "out_of_sequence",
          t("filter.outOfSequence", { count: counts.byKind.out_of_sequence })
        ),
        kindChip(
          "duplicate_number",
          t("filter.duplicate", { count: counts.byKind.duplicate_number })
        ),
        kindChip(
          "next_missing",
          t("filter.nextMissing", { count: counts.byKind.next_missing })
        ),
      ];
  const visibleFixed = fixedChips.filter((chip) => chip.count > 0);
  const visibleCheck = checkChips.filter((chip) => chip.count > 0);

  const renderChip = (chip: Chip) => (
    <SelectButton
      key={chip.filter}
      variant="select-heavy"
      size="sm"
      state={filter === chip.filter ? "selected" : "empty"}
      onClick={() => onFilterChange(chip.filter)}
    >
      {chip.label}
    </SelectButton>
  );

  return (
    <div className="flex shrink-0 flex-col gap-2 border-b border-border-01 bg-background-tint-00 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 max-w-full md:max-w-[28rem]">
          <Tooltip tooltip={title} side="bottom" align="start">
            <div className="min-w-0">
              <Text
                as="p"
                font="main-ui-action"
                color="text-05"
                maxLines={1}
                lang="am"
                dir="auto"
              >
                {title}
              </Text>
            </div>
          </Tooltip>
        </div>
        <Tag size="md" title={appliedLabel} />
        <Tag size="md" title={formatBytes(source.size_bytes)} />
        <Tag
          size="md"
          title={
            decisions
              ? t("source.decisions", { count: source.article_count })
              : t("source.articles", { count: source.article_count })
          }
        />
        {hasFrontMatter && <Tag size="md" title={t("source.frontMatter")} />}
        {!decisions && chapters > 0 && (
          <Tag size="md" title={t("source.chapters", { count: chapters })} />
        )}
        {decisions && source.volume && (
          <Tag
            size="md"
            title={t("source.volume", { volume: source.volume })}
          />
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {renderChip({
          filter: "all",
          label: t("filter.all", { count: counts.all }),
          count: counts.all,
        })}
        {counts.flagged > 0 ? (
          <>
            {renderChip({
              filter: "to_check",
              label: t("filter.toCheck", { count: counts.toCheck }),
              count: counts.toCheck,
            })}
            {visibleFixed.length > 0 && (
              <>
                {decisions ? (
                  <TierLabel />
                ) : (
                  <TierLabel label={t("filter.tierFixed")} />
                )}
                {visibleFixed.map(renderChip)}
              </>
            )}
            {visibleCheck.length > 0 && (
              <>
                <TierLabel label={t("filter.tierCheck")} />
                {visibleCheck.map(renderChip)}
              </>
            )}
          </>
        ) : (
          <Tag
            size="md"
            color="green"
            icon={SvgCheckCircle}
            title={t("source.noIssues")}
          />
        )}
        <div className="ms-auto w-52" title={t("source.splitAs")}>
          <div>
            <InputSingleSelect
              aria-label={t("source.splitAs")}
              value={profile}
              onValueChange={(value) => {
                if (isSplitProfile(value)) {
                  onProfileChange(value);
                }
              }}
              placeholder={t("source.splitAs")}
              options={profileOptions}
            />
          </div>
        </div>
      </div>

      {textBudgetExceeded && (
        <MessageCard
          variant="info"
          padding={1}
          title={t("source.budgetExceeded")}
        />
      )}
    </div>
  );
}

interface TierLabelProps {
  /** Omit for a plain divider. */
  label?: string;
}

/** Separates groups of filter chips: issues the splitter fixed, and possible wrong splits. */
function TierLabel({ label }: TierLabelProps) {
  return (
    <div className="flex items-center gap-2 ps-2">
      <div className="h-4 w-px bg-border-02" />
      {label && (
        <Text font="secondary-action" color="text-03">
          {label}
        </Text>
      )}
    </div>
  );
}

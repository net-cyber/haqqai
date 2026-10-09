"use client";

import { useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { EmptyMessageCard, type SelectOption } from "@opal/components";
import { cn } from "@opal/utils";
import type { SplitPreviewSource, SplitProfile } from "@/lib/fileConnector";
import { useSplitReviewState } from "@/lib/legalSplit/hooks";
import SplitSourceBand from "@/sections/legalSplit/SplitSourceBand";
import SplitUnitList from "@/sections/legalSplit/SplitUnitList";
import SplitUnitReader from "@/sections/legalSplit/SplitUnitReader";

interface SplitSourceReviewProps {
  source: SplitPreviewSource;
  /** Only the active review is shown and listens to the keyboard. */
  active: boolean;
  textBudgetExceeded: boolean;
  checked: ReadonlySet<string>;
  onCheckedChange: (keys: string[], value: boolean) => void;
  profile: SplitProfile;
  profileOptions: SelectOption[];
  profileLabel: (profile: string) => string;
  onProfileChange: (profile: SplitProfile) => void;
}

/** The review of one uploaded file: filters, outline and reader. */
export default function SplitSourceReview({
  source,
  active,
  textBudgetExceeded,
  checked,
  onCheckedChange,
  profile,
  profileOptions,
  profileLabel,
  onProfileChange,
}: SplitSourceReviewProps) {
  const t = useTranslations("admin.legalSplit.review.reader");
  const review = useSplitReviewState(source, checked, onCheckedChange);
  const selected = review.selectedUnit;
  const unitById = useCallback(
    (unitId: string) => source.units.find((unit) => unit.unit_id === unitId),
    [source.units]
  );
  const { onKeyDown, revealSelected } = review;
  // On the document, so the keys also work while a tab or the reader has focus.
  useEffect(() => {
    if (!active) {
      return;
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [active, onKeyDown]);
  useEffect(() => {
    if (active) {
      revealSelected();
    }
  }, [active, revealSelected]);

  return (
    <div
      className={cn(
        "min-h-0 flex-1 flex-col overflow-y-auto md:overflow-hidden",
        active ? "flex" : "hidden"
      )}
    >
      <SplitSourceBand
        source={source}
        counts={review.counts}
        filter={review.filter}
        onFilterChange={review.setFilter}
        profile={profile}
        profileOptions={profileOptions}
        profileLabel={profileLabel}
        onProfileChange={onProfileChange}
        textBudgetExceeded={textBudgetExceeded}
      />
      <div className="flex flex-col md:min-h-0 md:flex-1 md:flex-row">
        <SplitUnitList source={source} review={review} />
        {selected ? (
          <SplitUnitReader
            source={source}
            unit={selected}
            documentIndex={review.selectedIndex}
            previousUnit={review.previousUnit}
            nextUnit={review.nextUnit}
            position={review.position}
            isChecked={review.isChecked(selected)}
            unitById={unitById}
            onToggleChecked={review.toggleChecked}
            onPrevious={() => review.move(-1)}
            onNext={() => review.move(1)}
            onOpenUnit={review.openUnit}
            onShowLine={(line) => review.showLine(selected.unit_id, line)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6">
            <EmptyMessageCard sizePreset="main-ui" title={t("empty")} />
          </div>
        )}
      </div>
    </div>
  );
}

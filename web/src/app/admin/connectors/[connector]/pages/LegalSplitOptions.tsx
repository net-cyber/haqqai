"use client";

import { useCallback, useState } from "react";
import { useFormikContext } from "formik";
import { useTranslations } from "next-intl";
import { Button, InputSingleSelect, Text } from "@opal/components";
import { SvgListTree } from "@opal/icons";
import { isSplitProfile, type SplitProfile } from "@/lib/fileConnector";
import {
  useSplitPreview,
  useSplitProfileOptions,
} from "@/lib/legalSplit/hooks";
import SplitReviewModal from "@/sections/legalSplit/SplitReviewModal";
import SplitSummaryRows from "@/sections/legalSplit/SplitSummaryRows";

export const SPLIT_PROFILE_FIELD = "split_profile";

/** The File connector form fields this component reads and writes. */
export interface LegalSplitFormValues {
  file_locations?: File | File[] | null;
  split_profile?: string;
}

function asFiles(value: File | File[] | null | undefined): File[] {
  if (Array.isArray(value)) {
    return value;
  }
  return value ? [value] : [];
}

function filesSignature(files: File[]): string {
  return files
    .map((file) => `${file.name}:${file.size}:${file.lastModified}`)
    .join("|");
}

export function splitProfileFromValues(
  values: LegalSplitFormValues
): SplitProfile {
  const profile = values.split_profile;
  return profile && isSplitProfile(profile) ? profile : "none";
}

/** Split profile picker and the entry point to the split review. */
export default function LegalSplitOptions() {
  const t = useTranslations("admin.legalSplit");
  const { values, setFieldValue } = useFormikContext<LegalSplitFormValues>();
  const { options } = useSplitProfileOptions();

  const profile = splitProfileFromValues(values);
  const files = asFiles(values.file_locations);
  const signature = filesSignature(files);
  const viewKey = `${signature}|${profile}`;

  const [isReviewOpen, setReviewOpen] = useState(false);
  const [reviewedKey, setReviewedKey] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(() => new Set());
  const [activeSource, setActiveSource] = useState<string | null>(null);

  // Upload only while the review is open, or to keep showing a finished review.
  const enabled =
    files.length > 0 &&
    profile !== "none" &&
    (isReviewOpen || reviewedKey === viewKey);
  const { data, error, isLoading, mutate } = useSplitPreview(
    files,
    profile,
    signature,
    enabled
  );
  const reviewed = data !== undefined && reviewedKey === viewKey;

  const setProfile = useCallback(
    (next: SplitProfile) => {
      void setFieldValue(SPLIT_PROFILE_FIELD, next);
    },
    [setFieldValue]
  );

  const onCheckedChange = useCallback((keys: string[], value: boolean) => {
    setChecked((previous) => {
      const next = new Set(previous);
      for (const key of keys) {
        if (value) {
          next.add(key);
        } else {
          next.delete(key);
        }
      }
      return next;
    });
  }, []);

  const onOpenChange = (open: boolean) => {
    setReviewedKey(viewKey);
    setReviewOpen(open);
  };

  return (
    <div className="flex flex-col gap-2">
      <Text as="p" font="main-ui-action" color="text-04">
        {t("selector.label")}
      </Text>
      <Text as="p" font="secondary-body" color="text-03">
        {t("selector.description")}
      </Text>
      <InputSingleSelect
        value={profile}
        onValueChange={(value) => {
          if (isSplitProfile(value)) {
            setProfile(value);
          }
        }}
        placeholder={t("selector.placeholder")}
        options={options}
      />

      {profile !== "none" && (
        <div className="flex flex-col gap-2 pt-1">
          <div>
            <Button
              prominence="secondary"
              icon={SvgListTree}
              disabled={files.length === 0}
              onClick={() => onOpenChange(true)}
            >
              {reviewed ? t("review.entry.reopen") : t("review.entry.open")}
            </Button>
          </div>
          {files.length === 0 && (
            <Text as="p" font="secondary-body" color="text-03">
              {t("review.entry.noFiles")}
            </Text>
          )}
          {reviewed && !isReviewOpen && data && (
            <SplitSummaryRows sources={data.sources} checked={checked} />
          )}
        </div>
      )}

      <SplitReviewModal
        open={isReviewOpen}
        onOpenChange={onOpenChange}
        sources={data?.sources}
        isLoading={isLoading}
        error={error}
        onRetry={() => void mutate()}
        textBudgetExceeded={data?.text_budget_exceeded ?? false}
        viewKey={viewKey}
        uploadCount={files.length}
        activeSource={activeSource}
        onActiveSourceChange={setActiveSource}
        checked={checked}
        onCheckedChange={onCheckedChange}
        profile={profile}
        onProfileChange={setProfile}
      />
    </div>
  );
}

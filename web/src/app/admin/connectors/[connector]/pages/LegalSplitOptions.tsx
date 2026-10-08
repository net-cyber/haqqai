"use client";

import { useState } from "react";
import { useFormikContext } from "formik";
import { useTranslations } from "next-intl";
import { Button, InputSingleSelect, Text } from "@opal/components";
import { SvgEye } from "@opal/icons";
import {
  isSplitProfile,
  previewFileSplit,
  type SplitPreviewSource,
  type SplitProfile,
} from "@/lib/fileConnector";
import { useSplitProfileOptions } from "@/lib/legalSplit/hooks";

export const SPLIT_PROFILE_FIELD = "split_profile";

const PREVIEW_TITLE_COUNT = 5;
const PREVIEW_WARNING_COUNT = 5;

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
  return files.map((file) => `${file.name}:${file.size}`).join("|");
}

export function splitProfileFromValues(
  values: LegalSplitFormValues
): SplitProfile {
  const profile = values.split_profile;
  return profile && isSplitProfile(profile) ? profile : "none";
}

interface PreviewState {
  signature: string;
  profile: SplitProfile;
  sources: SplitPreviewSource[];
}

/** Split profile picker and preview for the File connector creation form. */
export default function LegalSplitOptions() {
  const t = useTranslations("admin.legalSplit");
  const { values, setFieldValue } = useFormikContext<LegalSplitFormValues>();
  const { options, labelFor } = useSplitProfileOptions();
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const profile = splitProfileFromValues(values);
  const files = asFiles(values.file_locations);
  const signature = filesSignature(files);
  const currentPreview =
    preview && preview.signature === signature && preview.profile === profile
      ? preview.sources
      : null;

  async function runPreview() {
    setIsLoading(true);
    setPreviewError(null);
    try {
      const response = await previewFileSplit(files, profile);
      setPreview({ signature, profile, sources: response.sources });
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsLoading(false);
    }
  }

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
        onValueChange={(value) => setFieldValue(SPLIT_PROFILE_FIELD, value)}
        placeholder={t("selector.placeholder")}
        options={options}
      />

      {profile !== "none" && (
        <div className="flex flex-col gap-2 pt-1">
          <div>
            <Button
              prominence="secondary"
              icon={SvgEye}
              onClick={runPreview}
              disabled={isLoading || files.length === 0}
            >
              {isLoading ? t("preview.loading") : t("preview.button")}
            </Button>
          </div>
          {files.length === 0 && (
            <Text as="p" font="secondary-body" color="text-03">
              {t("preview.noFiles")}
            </Text>
          )}
          {previewError && (
            <Text as="p" font="secondary-body" color="status-error-05">
              {t("preview.failed", { message: previewError })}
            </Text>
          )}
          {currentPreview && (
            <div className="flex flex-col gap-3 rounded-08 border border-border-02 p-3">
              <Text as="p" font="main-ui-action" color="text-04">
                {t("preview.title")}
              </Text>
              {currentPreview.map((source) => (
                <PreviewSource
                  key={source.source_name}
                  source={source}
                  profileLabel={labelFor(source.profile)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface PreviewSourceProps {
  source: SplitPreviewSource;
  profileLabel: string;
}

function PreviewSource({ source, profileLabel }: PreviewSourceProps) {
  const t = useTranslations("admin.legalSplit.preview");

  if (!source.splittable) {
    return (
      <Text as="p" font="secondary-body" color="text-03">
        {t("unsupported", { source: source.source_name })}
      </Text>
    );
  }
  if (source.unit_count === 0) {
    return (
      <Text as="p" font="secondary-body" color="status-error-05">
        {t("notSplit", { source: source.source_name })}
      </Text>
    );
  }

  const hiddenUnits = source.unit_count - PREVIEW_TITLE_COUNT;
  return (
    <div className="flex flex-col gap-1">
      <Text as="p" font="main-ui-body" color="text-04">
        {t("split", {
          source: source.source_name,
          count: source.unit_count,
          profile: profileLabel,
        })}
      </Text>
      <ul className="flex flex-col gap-0.5 ps-4">
        {source.units.slice(0, PREVIEW_TITLE_COUNT).map((unit) => (
          <Text
            key={unit.unit_id}
            as="li"
            font="secondary-body"
            color="text-03"
            maxLines={1}
          >
            {unit.display_name}
          </Text>
        ))}
      </ul>
      {hiddenUnits > 0 && (
        <Text as="p" font="secondary-body" color="text-03">
          {t("moreUnits", { count: hiddenUnits })}
        </Text>
      )}
      {source.warnings.length > 0 && (
        <>
          <Text as="p" font="secondary-action" color="text-04">
            {t("warnings", { count: source.warnings.length })}
          </Text>
          <ul className="flex flex-col gap-0.5 ps-4">
            {source.warnings.slice(0, PREVIEW_WARNING_COUNT).map((warning) => (
              <Text
                key={warning}
                as="li"
                font="secondary-body"
                color="text-03"
                maxLines={1}
              >
                {warning}
              </Text>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

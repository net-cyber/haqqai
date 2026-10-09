"use client";

import { useTranslations } from "next-intl";
import {
  Button,
  InputSingleSelect,
  MessageCard,
  Text,
  type SelectOption,
} from "@opal/components";
import {
  isSplitProfile,
  type SplitPreviewSource,
  type SplitProfile,
} from "@/lib/fileConnector";

interface SplitKeptWholeNoticeProps {
  source: SplitPreviewSource;
  /** True when this is the only upload, so changing the profile affects only it. */
  canResplit: boolean;
  profile: SplitProfile;
  profileOptions: SelectOption[];
  profileLabel: (profile: string) => string;
  onProfileChange: (profile: SplitProfile) => void;
}

/** Why a file is imported as one document, and how to split it anyway. */
export default function SplitKeptWholeNotice({
  source,
  canResplit,
  profile,
  profileOptions,
  profileLabel,
  onProfileChange,
}: SplitKeptWholeNoticeProps) {
  const t = useTranslations("admin.legalSplit.review");
  const kept = source.kept_whole;

  if (!source.splittable) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-[36rem]">
          <MessageCard
            variant="default"
            title={t("unsupported.title")}
            description={t("unsupported.body", { name: source.source_name })}
          />
        </div>
      </div>
    );
  }

  const suggested = kept?.suggested_profile ?? null;
  const description =
    kept?.reason === "auto_too_few"
      ? t("keptWhole.autoTooFew", {
          found: kept.found ?? 0,
          minimum: kept.minimum ?? 0,
        })
      : kept?.reason === "too_few_units"
        ? t("keptWhole.tooFewUnits", {
            profile: profileLabel(source.requested_profile),
            found: kept.found ?? 0,
            minimum: kept.minimum ?? 0,
          })
        : t("keptWhole.notSplit");

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-[36rem]">
        <MessageCard
          variant="info"
          title={t("keptWhole.title")}
          description={description}
          bottomChildren={
            <div className="flex flex-col gap-3">
              {suggested !== null &&
                (canResplit ? (
                  <div>
                    <Button
                      prominence="secondary"
                      onClick={() => onProfileChange(suggested)}
                    >
                      {t("keptWhole.splitAs", {
                        profile: profileLabel(suggested),
                      })}
                    </Button>
                  </div>
                ) : (
                  <Text font="secondary-body" color="text-04">
                    {t("keptWhole.uploadAlone", {
                      profile: profileLabel(suggested),
                    })}
                  </Text>
                ))}
              {/* Any profile can be chosen here, so a wrong choice is never a dead end. */}
              <div className="flex flex-col gap-1">
                <Text font="secondary-action" color="text-04">
                  {t("source.splitAs")}
                </Text>
                <div className="w-full max-w-[16rem]">
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
          }
        />
      </div>
    </div>
  );
}

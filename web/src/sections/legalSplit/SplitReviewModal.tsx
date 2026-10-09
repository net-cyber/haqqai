"use client";

import { useEffect } from "react";
import { useFormikContext } from "formik";
import { useTranslations } from "next-intl";
import {
  Button,
  EmptyMessageCard,
  IconLoader,
  MessageCard,
  Modal,
  ProgressBar,
  Tabs,
  Text,
} from "@opal/components";
import {
  SvgAlertTriangle,
  SvgCheckCircle,
  SvgFileText,
  SvgListTree,
} from "@opal/icons";
import { cn } from "@opal/utils";
import type { SplitPreviewSource, SplitProfile } from "@/lib/fileConnector";
import { useSplitProfileOptions } from "@/lib/legalSplit/hooks";
import { countsFor, sourceFileCount } from "@/lib/legalSplit/review";
import SplitKeptWholeNotice from "@/sections/legalSplit/SplitKeptWholeNotice";
import SplitSourceReview from "@/sections/legalSplit/SplitSourceReview";

const SKELETON_ROWS = 8;

interface SplitReviewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sources: SplitPreviewSource[] | undefined;
  isLoading: boolean;
  error: Error | undefined;
  onRetry: () => void;
  textBudgetExceeded: boolean;
  /** Changes when the files or the profile change, to reset each source's view. */
  viewKey: string;
  uploadCount: number;
  activeSource: string | null;
  onActiveSourceChange: (sourceName: string) => void;
  checked: ReadonlySet<string>;
  onCheckedChange: (keys: string[], value: boolean) => void;
  profile: SplitProfile;
  onProfileChange: (profile: SplitProfile) => void;
}

function isKeptWhole(source: SplitPreviewSource): boolean {
  return source.units.length === 0;
}

/** True when Escape should close an open dropdown, not the review. */
function isOpenCombobox(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    target.closest('[role="combobox"][aria-expanded="true"]') !== null
  );
}

/** Full-window review of a split before the connector is created. */
export default function SplitReviewModal({
  open,
  onOpenChange,
  sources,
  isLoading,
  error,
  onRetry,
  textBudgetExceeded,
  viewKey,
  uploadCount,
  activeSource,
  onActiveSourceChange,
  checked,
  onCheckedChange,
  profile,
  onProfileChange,
}: SplitReviewModalProps) {
  const t = useTranslations("admin.legalSplit.review");
  const { submitForm, isSubmitting } = useFormikContext();
  const { options, labelFor } = useSplitProfileOptions();
  const splitOptions = options.filter((option) => option.value !== "none");

  const list = sources ?? [];
  const sourceCounts = list.map((source) => ({
    source,
    counts: countsFor(source, checked),
  }));
  const defaultSource =
    sourceCounts.find(({ counts }) => counts.toCheck > 0)?.source ?? list[0];
  const active =
    list.find((source) => source.source_name === activeSource) ?? defaultSource;

  // Pick the first tab once per review run, so check marks never switch tabs.
  const defaultSourceName = defaultSource?.source_name ?? null;
  const hasActiveSource =
    activeSource !== null &&
    (sources ?? []).some((source) => source.source_name === activeSource);
  useEffect(() => {
    if (!hasActiveSource && defaultSourceName !== null) {
      onActiveSourceChange(defaultSourceName);
    }
  }, [defaultSourceName, hasActiveSource, onActiveSourceChange]);

  const files = list.reduce(
    (total, source) => total + sourceFileCount(source),
    0
  );
  const flagged = sourceCounts.reduce(
    (total, { counts }) => total + counts.flagged,
    0
  );
  const checkedTotal = sourceCounts.reduce(
    (total, { counts }) => total + counts.checked,
    0
  );
  const creates = t("footer.creates", { files, sources: list.length });

  const tabLabel = (source: SplitPreviewSource, toCheck: number): string =>
    !source.splittable
      ? t("tab.notSplit", { name: source.source_name })
      : isKeptWhole(source)
        ? t("tab.keptWhole", { name: source.source_name })
        : t("tab.label", { name: source.source_name, toCheck });

  const close = () => onOpenChange(false);

  const body = isLoading ? (
    <SplitReviewSkeleton uploadCount={uploadCount} />
  ) : error ? (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-[36rem]">
        <MessageCard
          variant="error"
          title={t("failed.title")}
          description={error.message}
          rightChildren={
            <Button prominence="secondary" onClick={onRetry}>
              {t("failed.retry")}
            </Button>
          }
        />
      </div>
    </div>
  ) : sources === undefined ? (
    <SplitReviewSkeleton uploadCount={uploadCount} />
  ) : list.length === 0 ? (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-[36rem]">
        <EmptyMessageCard
          sizePreset="main-ui"
          title={t("empty.title")}
          description={t("empty.description")}
        />
      </div>
    </div>
  ) : (
    list.map((source) => {
      const isActive = source === active;
      if (isKeptWhole(source)) {
        return (
          <div
            key={`${viewKey}|${source.source_name}`}
            className={cn("min-h-0 flex-1", isActive ? "flex" : "hidden")}
          >
            <SplitKeptWholeNotice
              source={source}
              canResplit={list.length === 1}
              profile={profile}
              profileOptions={splitOptions}
              profileLabel={labelFor}
              onProfileChange={onProfileChange}
            />
          </div>
        );
      }
      // Every review stays mounted, so each tab keeps its filter, search and selection.
      return (
        <SplitSourceReview
          key={`${viewKey}|${source.source_name}`}
          source={source}
          active={isActive}
          textBudgetExceeded={textBudgetExceeded}
          checked={checked}
          onCheckedChange={onCheckedChange}
          profile={profile}
          profileOptions={splitOptions}
          profileLabel={labelFor}
          onProfileChange={onProfileChange}
        />
      );
    })
  );

  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <Modal.Content
        width="full"
        height="full"
        preventAccidentalClose={false}
        onEscapeKeyDown={(event) => {
          if (isOpenCombobox(event.target)) {
            event.preventDefault();
          }
        }}
      >
        <Modal.Header
          icon={SvgListTree}
          title={t("title")}
          description={t("description")}
          onClose={close}
        >
          {list.length >= 2 && active && (
            <Tabs
              variant="pill"
              value={active.source_name}
              onValueChange={onActiveSourceChange}
            >
              <Tabs.List enableScrollArrows>
                {sourceCounts.map(({ source, counts }) => (
                  <Tabs.Trigger
                    key={source.source_name}
                    value={source.source_name}
                    icon={
                      isKeptWhole(source)
                        ? SvgFileText
                        : counts.toCheck > 0
                          ? SvgAlertTriangle
                          : SvgCheckCircle
                    }
                  >
                    {tabLabel(source, counts.toCheck)}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
            </Tabs>
          )}
        </Modal.Header>

        <div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-background-tint-01">
          {body}
        </div>

        <Modal.Footer>
          <div className="flex w-full flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex min-w-0 items-center gap-2">
              {list.length > 0 && !isLoading && (
                <>
                  {flagged > 0 && (
                    <div className="w-24 shrink-0 rounded-04 border border-border-02">
                      <ProgressBar
                        color="green"
                        value={checkedTotal}
                        max={flagged}
                      />
                    </div>
                  )}
                  <Text font="secondary-body" color="text-03">
                    {flagged > 0
                      ? t("footer.progress", {
                          checked: checkedTotal,
                          total: flagged,
                          creates,
                        })
                      : t("footer.nothingToCheck", { creates })}
                  </Text>
                </>
              )}
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button prominence="secondary" onClick={close}>
                {t("footer.back")}
              </Button>
              <Button
                disabled={isSubmitting}
                onClick={() => {
                  close();
                  void submitForm();
                }}
              >
                {list.length > 0 && !isLoading
                  ? t("footer.create", { count: files })
                  : t("footer.createPending")}
              </Button>
            </div>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

interface SplitReviewSkeletonProps {
  uploadCount: number;
}

function SplitReviewSkeleton({ uploadCount }: SplitReviewSkeletonProps) {
  const t = useTranslations("admin.legalSplit.review");
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b border-border-01 bg-background-tint-00 px-4 py-3">
        <IconLoader size={16} />
        <Text font="secondary-body" color="text-03">
          {t("loading", { count: uploadCount })}
        </Text>
      </div>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="flex h-96 shrink-0 flex-col gap-2 border-b border-border-01 p-3 md:h-auto md:w-[22rem] md:border-b-0 md:border-e">
          {Array.from({ length: SKELETON_ROWS }, (_, index) => (
            <div
              key={index}
              className="h-7 animate-pulse rounded-04 bg-background-tint-02"
            />
          ))}
        </div>
        <div className="flex flex-1 items-center justify-center bg-background-tint-00">
          <IconLoader />
        </div>
      </div>
    </div>
  );
}

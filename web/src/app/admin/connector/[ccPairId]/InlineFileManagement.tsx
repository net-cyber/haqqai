"use client";

import { useState, useRef } from "react";
import { useTranslations } from "next-intl";
import { Button, InputSingleSelect, Text as OpalText } from "@opal/components";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { InputCheckbox } from "@opal/components";
import {
  isSplitProfile,
  updateConnectorFiles,
  type ConnectorFileInfo,
  type SplitProfile,
} from "@/lib/fileConnector";
import {
  useSplitProfileOptions,
  useSplitSummaryToast,
} from "@/lib/legalSplit/hooks";
import ConnectorFileEditorModal from "@/app/admin/connector/[ccPairId]/ConnectorFileEditorModal";
import { toast } from "@opal/layouts";
import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import SvgSimpleLoader from "@opal/icons/simple-loader";
import { Modal } from "@opal/components";
import Text from "@/refresh-components/texts/Text";
import {
  SvgCheck,
  SvgChevronDown,
  SvgChevronRight,
  SvgEdit,
  SvgFileText,
  SvgFolderPlus,
  SvgPlusCircle,
  SvgX,
} from "@opal/icons";
import { formatBytes } from "@/lib/utils";
import { timestampToReadableDate } from "@/lib/dateUtils";

interface InlineFileManagementProps {
  connectorId: number;
  onRefresh: () => void;
}

/** Files split from the same source file, in listing order. */
function groupBySource(
  files: ConnectorFileInfo[]
): [string, ConnectorFileInfo[]][] {
  const groups = new Map<string, ConnectorFileInfo[]>();
  files.forEach((file) => {
    if (!file.parent_file_name) {
      return;
    }
    const group = groups.get(file.parent_file_name) ?? [];
    group.push(file);
    groups.set(file.parent_file_name, group);
  });
  return Array.from(groups.entries());
}

export default function InlineFileManagement({
  connectorId,
  onRefresh,
}: InlineFileManagementProps) {
  const t = useTranslations("admin.connector");
  const tSplit = useTranslations("admin.legalSplit");
  const { options: splitOptions } = useSplitProfileOptions();
  const showSplitSummary = useSplitSummaryToast();
  const [splitProfile, setSplitProfile] = useState<SplitProfile>("none");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [editingFile, setEditingFile] = useState<ConnectorFileInfo | null>(
    null
  );
  const [isEditing, setIsEditing] = useState(false);
  const [selectedFilesToRemove, setSelectedFilesToRemove] = useState<
    Set<string>
  >(new Set());
  const [filesToAdd, setFilesToAdd] = useState<File[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    data: filesResponse,
    isLoading,
    error,
    mutate: refreshFiles,
  } = useSWR<{ files: ConnectorFileInfo[] }>(
    `/api/manage/admin/connector/${connectorId}/files`,
    errorHandlingFetcher
    // No refreshInterval: the file list only changes through this component's
    // own save flow, which calls refreshFiles() explicitly.
  );

  const files = filesResponse?.files || [];

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    setFilesToAdd((prev) => [...prev, ...Array.from(selectedFiles)]);
    // Reset the input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveNewFile = (index: number) => {
    setFilesToAdd((prev) => prev.filter((_, i) => i !== index));
  };

  const toggleGroup = (source: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(source)) {
        next.delete(source);
      } else {
        next.add(source);
      }
      return next;
    });
  };

  const toggleGroupForRemoval = (groupFiles: ConnectorFileInfo[]) => {
    setSelectedFilesToRemove((prev) => {
      const next = new Set(prev);
      const allSelected = groupFiles.every((file) => next.has(file.file_id));
      groupFiles.forEach((file) => {
        if (allSelected) {
          next.delete(file.file_id);
        } else {
          next.add(file.file_id);
        }
      });
      return next;
    });
  };

  const toggleFileForRemoval = (fileId: string) => {
    setSelectedFilesToRemove((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(fileId)) {
        newSet.delete(fileId);
      } else {
        newSet.add(fileId);
      }
      return newSet;
    });
  };

  const handleSaveClick = () => {
    // Validate that we won't remove all files
    const remainingFiles = files.filter(
      (file) => !selectedFilesToRemove.has(file.file_id)
    ).length;

    if (remainingFiles === 0 && filesToAdd.length === 0) {
      toast.error(t("fileManagement.toasts.cannotRemoveAllFiles"));
      return;
    }

    // Show confirmation modal
    setShowSaveConfirm(true);
  };

  const handleConfirmSave = async () => {
    setShowSaveConfirm(false);
    setIsSaving(true);
    try {
      const result = await updateConnectorFiles(
        connectorId,
        Array.from(selectedFilesToRemove),
        filesToAdd,
        splitProfile
      );

      toast.success(t("fileManagement.toasts.filesUpdated"));
      showSplitSummary(result.split_summary);

      // Reset editing state
      setIsEditing(false);
      setSelectedFilesToRemove(new Set());
      setFilesToAdd([]);
      setSplitProfile("none");

      // Refresh data
      refreshFiles();
      onRefresh();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : t("fileManagement.toasts.updateFailed")
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setSelectedFilesToRemove(new Set());
    setFilesToAdd([]);
    setSplitProfile("none");
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <SvgSimpleLoader className="h-6 w-6" />
      </div>
    );
  }

  if (error) {
    return (
      <Text as="p" className="text-error">
        {t("fileManagement.loadError", { message: error.message })}
      </Text>
    );
  }

  const currentFiles = files.filter(
    (file) => !selectedFilesToRemove.has(file.file_id)
  );
  const totalFiles = currentFiles.length + filesToAdd.length;
  const standaloneFiles = files.filter((file) => !file.parent_file_name);
  const fileGroups = groupBySource(files);

  const renderFileRow = (file: ConnectorFileInfo, nested: boolean) => {
    const isMarkedForRemoval = selectedFilesToRemove.has(file.file_id);
    return (
      <TableRow
        key={file.file_id}
        className={isMarkedForRemoval ? "bg-red-100 dark:bg-red-900/20" : ""}
      >
        {isEditing && (
          <TableCell>
            <InputCheckbox
              checked={isMarkedForRemoval}
              onCheckedChange={() => toggleFileForRemoval(file.file_id)}
            />
          </TableCell>
        )}
        <TableCell className={nested ? "font-medium ps-10" : "font-medium"}>
          <span className={isMarkedForRemoval ? "line-through opacity-60" : ""}>
            {file.file_name}
          </span>
          {isMarkedForRemoval && (
            <span className="ms-2 text-xs font-semibold text-red-600 dark:text-red-400">
              {t("fileManagement.removingBadge.label")}
            </span>
          )}
        </TableCell>
        <TableCell
          className={isMarkedForRemoval ? "line-through opacity-60" : ""}
        >
          {formatBytes(file.file_size)}
        </TableCell>
        <TableCell
          className={isMarkedForRemoval ? "line-through opacity-60" : ""}
        >
          {file.upload_date ? timestampToReadableDate(file.upload_date) : "-"}
        </TableCell>
        <TableCell>
          {!isEditing && file.editable && (
            <Button
              icon={SvgFileText}
              prominence="tertiary"
              size="sm"
              onClick={() => setEditingFile(file)}
              tooltip={t("fileManagement.editContentButton.tooltip")}
              title={t("fileManagement.editContentButton.tooltip")}
            />
          )}
        </TableCell>
      </TableRow>
    );
  };

  return (
    <>
      {/* Header with Edit/Save buttons */}
      <div className="flex justify-between items-center mb-4">
        <Text as="p" mainUiBody>
          {t("fileManagement.header.title", { count: totalFiles })}
        </Text>
        <div className="flex gap-2">
          {!isEditing ? (
            <Button
              prominence="secondary"
              onClick={() => setIsEditing(true)}
              icon={SvgEdit}
            >
              {t("fileManagement.editButton.label")}
            </Button>
          ) : (
            <>
              <Button
                disabled={isSaving}
                prominence="secondary"
                onClick={handleCancel}
                icon={SvgX}
              >
                {t("fileManagement.cancelButton.label")}
              </Button>
              <Button
                disabled={
                  isSaving ||
                  (selectedFilesToRemove.size === 0 && filesToAdd.length === 0)
                }
                onClick={handleSaveClick}
                icon={SvgCheck}
              >
                {isSaving
                  ? t("fileManagement.saveButton.saving")
                  : t("fileManagement.saveButton.label")}
              </Button>
            </>
          )}
        </div>
      </div>

      {/* File List */}
      {files.length === 0 && filesToAdd.length === 0 ? (
        <Text as="p" mainUiMuted className="text-center py-8">
          {t("fileManagement.empty.description")}
        </Text>
      ) : (
        <div className="border rounded-lg overflow-hidden mb-4">
          {/* Scrollable container with max height */}
          <div className="max-h-[400px] overflow-y-auto">
            <Table>
              <TableHeader className="sticky top-0 bg-background z-10">
                <TableRow>
                  {isEditing && <TableHead className="w-12"></TableHead>}
                  <TableHead>{t("fileManagement.columns.fileName")}</TableHead>
                  <TableHead>{t("fileManagement.columns.size")}</TableHead>
                  <TableHead>
                    {t("fileManagement.columns.uploadDate")}
                  </TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Files uploaded as they are */}
                {standaloneFiles.map((file) => renderFileRow(file, false))}

                {/* Files split from one legal source file */}
                {fileGroups.map(([source, groupFiles]) => {
                  const isExpanded = expandedGroups.has(source);
                  const allMarked = groupFiles.every((file) =>
                    selectedFilesToRemove.has(file.file_id)
                  );
                  return [
                    <TableRow key={`group-${source}`}>
                      {isEditing && (
                        <TableCell>
                          <InputCheckbox
                            checked={allMarked}
                            onCheckedChange={() =>
                              toggleGroupForRemoval(groupFiles)
                            }
                          />
                        </TableCell>
                      )}
                      <TableCell colSpan={3}>
                        <div className="flex items-center gap-2">
                          <Button
                            icon={isExpanded ? SvgChevronDown : SvgChevronRight}
                            prominence="tertiary"
                            size="sm"
                            onClick={() => toggleGroup(source)}
                            tooltip={
                              isExpanded
                                ? t("fileManagement.groups.collapse")
                                : t("fileManagement.groups.expand")
                            }
                            title={
                              isExpanded
                                ? t("fileManagement.groups.collapse")
                                : t("fileManagement.groups.expand")
                            }
                          />
                          <OpalText font="main-ui-action" color="text-04">
                            {source}
                          </OpalText>
                          <OpalText font="secondary-body" color="text-03">
                            {t("fileManagement.groups.fileCount", {
                              count: groupFiles.length,
                            })}
                          </OpalText>
                        </div>
                      </TableCell>
                      <TableCell />
                    </TableRow>,
                    ...(isExpanded
                      ? groupFiles.map((file) => renderFileRow(file, true))
                      : []),
                  ];
                })}

                {/* New files to be added */}
                {filesToAdd.map((file, index) => (
                  <TableRow
                    key={`new-${index}`}
                    className="bg-green-50 dark:bg-green-900/10"
                  >
                    {isEditing && (
                      <TableCell>
                        <Button
                          icon={SvgX}
                          variant="danger"
                          prominence="tertiary"
                          size="sm"
                          onClick={() => handleRemoveNewFile(index)}
                          tooltip={t("fileManagement.removeFileButton.tooltip")}
                          title={t("fileManagement.removeFileButton.tooltip")}
                        />
                      </TableCell>
                    )}
                    <TableCell className="font-medium">
                      {file.name}
                      <Text as="p" figureSmallValue>
                        {t("fileManagement.newBadge.label")}
                      </Text>
                    </TableCell>
                    <TableCell>{formatBytes(file.size)}</TableCell>
                    <TableCell>-</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Add Files Button (only in edit mode) */}
      {isEditing && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="flex max-w-md flex-col gap-1">
            <OpalText font="main-ui-action" color="text-04">
              {tSplit("selector.label")}
            </OpalText>
            <InputSingleSelect
              value={splitProfile}
              onValueChange={(value) =>
                setSplitProfile(isSplitProfile(value) ? value : "none")
              }
              placeholder={tSplit("selector.placeholder")}
              options={splitOptions}
            />
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              id={`file-upload-${connectorId}`}
            />
            <Button
              disabled={isSaving}
              prominence="secondary"
              onClick={() => fileInputRef.current?.click()}
              icon={SvgPlusCircle}
            >
              {t("fileManagement.addFilesButton.label")}
            </Button>
          </div>
        </div>
      )}

      <ConnectorFileEditorModal
        connectorId={connectorId}
        file={editingFile}
        onClose={() => setEditingFile(null)}
        onSaved={() => {
          refreshFiles();
          onRefresh();
        }}
      />

      {/* Confirmation Modal */}
      <Modal open={showSaveConfirm} onOpenChange={setShowSaveConfirm}>
        <Modal.Content width="sm">
          <Modal.Header
            icon={SvgFolderPlus}
            title={t("fileManagement.confirmModal.title")}
            description={t("fileManagement.confirmModal.description")}
          />

          <Modal.Body>
            {selectedFilesToRemove.size > 0 && (
              <div className="p-3 bg-red-50 dark:bg-red-900/10 rounded-md">
                <Text
                  as="p"
                  mainUiBody
                  className="font-semibold text-red-800 dark:text-red-200"
                >
                  {t("fileManagement.confirmModal.removeSummary", {
                    count: selectedFilesToRemove.size,
                  })}
                </Text>
                <Text
                  as="p"
                  secondaryBody
                  className="text-red-700 dark:text-red-300 mt-1"
                >
                  {t("fileManagement.confirmModal.removeDetails")}
                </Text>
              </div>
            )}

            {filesToAdd.length > 0 && (
              <div className="p-3 bg-green-50 dark:bg-green-900/10 rounded-md">
                <Text
                  as="p"
                  mainUiBody
                  className="font-semibold text-green-800 dark:text-green-200"
                >
                  {t("fileManagement.confirmModal.addSummary", {
                    count: filesToAdd.length,
                  })}
                </Text>
                <Text
                  as="p"
                  secondaryBody
                  className="text-green-700 dark:text-green-300 mt-1"
                >
                  {t("fileManagement.confirmModal.addDetails")}
                </Text>
              </div>
            )}
          </Modal.Body>

          <Modal.Footer>
            <Button
              disabled={isSaving}
              prominence="secondary"
              onClick={() => setShowSaveConfirm(false)}
            >
              {t("fileManagement.cancelButton.label")}
            </Button>
            <Button disabled={isSaving} onClick={handleConfirmSave}>
              {isSaving
                ? t("fileManagement.saveButton.saving")
                : t("fileManagement.confirmModal.confirmButton.label")}
            </Button>
          </Modal.Footer>
        </Modal.Content>
      </Modal>
    </>
  );
}

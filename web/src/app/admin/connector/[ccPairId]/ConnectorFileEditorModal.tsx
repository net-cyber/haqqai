"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { useTranslations } from "next-intl";
import {
  BasicModalFooter,
  Button,
  InputTextArea,
  Modal,
  Text,
} from "@opal/components";
import { SvgEdit } from "@opal/icons";
import SvgSimpleLoader from "@opal/icons/simple-loader";
import { toast } from "@opal/layouts";
import { errorHandlingFetcher } from "@/lib/fetcher";
import {
  connectorFileContentUrl,
  saveConnectorFileContent,
  type ConnectorFileContent,
  type ConnectorFileInfo,
} from "@/lib/fileConnector";

interface ConnectorFileEditorModalProps {
  connectorId: number;
  /** The file to edit. The modal is closed while this is null. */
  file: ConnectorFileInfo | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Edit the text of one File connector file and re-index it. */
export default function ConnectorFileEditorModal({
  connectorId,
  file,
  onClose,
  onSaved,
}: ConnectorFileEditorModalProps) {
  const t = useTranslations("admin.connector.fileManagement.editModal");
  const { data, error, isLoading, mutate } = useSWR<ConnectorFileContent>(
    file ? connectorFileContentUrl(connectorId, file.file_id) : null,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  const [draft, setDraft] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const fileId = file?.file_id;
  useEffect(() => {
    setDraft(null);
  }, [fileId]);

  const text = draft ?? data?.content ?? "";

  async function handleSave() {
    if (!file) {
      return;
    }
    if (!text.trim()) {
      toast.error(t("emptyError"));
      return;
    }
    setIsSaving(true);
    try {
      const saved = await saveConnectorFileContent(
        connectorId,
        file.file_id,
        text
      );
      await mutate(saved, { revalidate: false });
      toast.success(t("saved"));
      onSaved();
      onClose();
    } catch (saveError) {
      toast.error(
        t("saveFailed", {
          message:
            saveError instanceof Error ? saveError.message : String(saveError),
        })
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      open={file !== null}
      onOpenChange={(open) => {
        if (!open && !isSaving) {
          onClose();
        }
      }}
    >
      <Modal.Content width="lg" height="lg">
        <Modal.Header
          icon={SvgEdit}
          title={t("title", { fileName: file?.file_name ?? "" })}
          description={t("description")}
          onClose={isSaving ? undefined : onClose}
        />
        <Modal.Body>
          {isLoading ? (
            <div className="flex justify-center py-12">
              <SvgSimpleLoader className="h-6 w-6" />
            </div>
          ) : error ? (
            <Text as="p" font="main-ui-body" color="status-error-05">
              {t("loadError", { message: error.message })}
            </Text>
          ) : (
            <InputTextArea
              value={text}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("placeholder")}
              rows={20}
              dir="auto"
            />
          )}
        </Modal.Body>
        <Modal.Footer>
          <BasicModalFooter
            cancel={
              <Button
                prominence="secondary"
                disabled={isSaving}
                onClick={onClose}
              >
                {t("cancel")}
              </Button>
            }
            submit={
              <Button
                disabled={isSaving || isLoading || !!error || draft === null}
                onClick={handleSave}
              >
                {isSaving ? t("saving") : t("save")}
              </Button>
            }
          />
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

import type { ErrorResponseBody } from "@/lib/fetcher";

export interface ConnectorFileInfo {
  file_id: string;
  file_name: string;
  file_size?: number;
  upload_date?: string;
  document_id?: string | null;
  editable?: boolean;
  // Set on files created by splitting a larger legal file.
  parent_file_name?: string | null;
  unit_id?: string | null;
  unit_type?: string | null;
  unit_title?: string | null;
}

export interface ConnectorFilesResponse {
  files: ConnectorFileInfo[];
}

export const SPLIT_PROFILES = [
  "none",
  "auto",
  "proclamation",
  "civil_code",
  "cassation",
] as const;

export type SplitProfile = (typeof SPLIT_PROFILES)[number];

export function isSplitProfile(value: string): value is SplitProfile {
  return SPLIT_PROFILES.some((profile) => profile === value);
}

export interface SplitSummary {
  source_name: string;
  // The applied profile: "auto" is resolved, "none" means the file stayed whole.
  profile: string;
  unit_count: number;
  warnings: string[];
}

export interface FileUploadResponse {
  file_paths: string[];
  file_names: string[];
  zip_metadata_file_id: string | null;
  split_summary?: SplitSummary[] | null;
}

export interface SplitPreviewUnit {
  unit_id: string;
  display_name: string;
  unit_type: string;
  chars: number;
}

export interface SplitPreviewSource {
  source_name: string;
  splittable: boolean;
  profile: string;
  unit_count: number;
  article_count: number;
  units: SplitPreviewUnit[];
  warnings: string[];
}

export interface SplitPreviewResponse {
  sources: SplitPreviewSource[];
}

export interface ConnectorFileContent {
  file_id: string;
  file_name: string;
  content: string;
  metadata: Record<string, string>;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: ErrorResponseBody = await response.json();
    return body.detail || `${response.status}`;
  } catch {
    return `${response.status}`;
  }
}

export async function updateConnectorFiles(
  connectorId: number,
  fileIdsToRemove: string[],
  filesToAdd: File[],
  splitProfile: SplitProfile = "none"
): Promise<FileUploadResponse> {
  const formData = new FormData();

  // Add files to remove as JSON
  formData.append("file_ids_to_remove", JSON.stringify(fileIdsToRemove));
  formData.append("split_profile", splitProfile);

  // Add new files
  filesToAdd.forEach((file) => {
    formData.append("files", file);
  });

  const response = await fetch(
    `/api/manage/admin/connector/${connectorId}/files/update`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error(
      `Failed to update connector files (${response.status}): ${await errorDetail(
        response
      )}`
    );
  }
  return response.json();
}

export async function previewFileSplit(
  files: File[],
  splitProfile: SplitProfile
): Promise<SplitPreviewResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("split_profile", splitProfile);

  const response = await fetch(
    "/api/manage/admin/connector/file/split-preview",
    {
      method: "POST",
      body: formData,
    }
  );
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return response.json();
}

export function connectorFileContentUrl(
  connectorId: number,
  fileId: string
): string {
  return `/api/manage/admin/connector/${connectorId}/files/${encodeURIComponent(
    fileId
  )}/content`;
}

export async function saveConnectorFileContent(
  connectorId: number,
  fileId: string,
  content: string
): Promise<ConnectorFileContent> {
  const response = await fetch(connectorFileContentUrl(connectorId, fileId), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new Error(await errorDetail(response));
  }
  return response.json();
}

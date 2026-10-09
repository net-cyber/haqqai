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

export type SplitCaseField = "date" | "applicant" | "respondent";
export type SplitPathLevel =
  | "book"
  | "part"
  | "chapter"
  | "section"
  | "subsection";
export type SplitUnitType =
  | "proclamation_article"
  | "civil_code_article"
  | "cassation_decision"
  | "front_matter";

export interface NumberRepairedIssue {
  kind: "number_repaired";
  /** The number as written in the source heading, e.g. "፰". */
  source_number: string;
  source_line: string;
}

export interface OutOfSequenceIssue {
  kind: "out_of_sequence";
}

export interface DuplicateNumberIssue {
  kind: "duplicate_number";
  other_unit_ids: string[];
  /** Characters that differ from other_unit_ids[0]; 0 means the same text. */
  differing_chars: number;
}

export interface NextMissingIssue {
  kind: "next_missing";
  from_number: number;
  to_number: number;
  from_text: string;
  to_text: string;
  /** 0-based line in this unit's text that looks like the missing heading. */
  suspect_line: number | null;
  suspect_text: string | null;
}

export interface MissingFieldsIssue {
  kind: "missing_fields";
  fields: SplitCaseField[];
  searched_lines: number;
}

export type SplitPreviewIssue =
  | NumberRepairedIssue
  | OutOfSequenceIssue
  | DuplicateNumberIssue
  | NextMissingIssue
  | MissingFieldsIssue;

export type SplitIssueKind = SplitPreviewIssue["kind"];

export interface SplitPathCrumb {
  level: SplitPathLevel;
  label: string;
}

export interface SplitPreviewUnit {
  unit_id: string;
  unit_type: SplitUnitType;
  /** The file name the unit is stored under, e.g. "family__art-60.md". */
  file_name: string;
  /** "አንቀጽ ፷", "ሰበር መ/ቁ 94952", or "" for front matter. */
  label: string;
  heading: string;
  number: number | null;
  number_text: string | null;
  /** First line of the unit header within `text`. */
  header_start: number;
  /** Lines the unit header spans, from `header_start`. */
  header_lines: number;
  path: SplitPathCrumb[];
  case_number: string | null;
  date: string | null;
  applicant: string | null;
  respondent: string | null;
  /** Length of the full text, also when `text` is an excerpt. */
  chars: number;
  text: string;
  text_truncated: boolean;
  issues: SplitPreviewIssue[];
}

export interface SplitKeptWhole {
  reason: "unsupported_type" | "auto_too_few" | "too_few_units";
  found: number | null;
  minimum: number | null;
  suggested_profile: "proclamation" | "civil_code" | "cassation" | null;
}

export interface SplitPreviewSource {
  source_name: string;
  size_bytes: number;
  splittable: boolean;
  requested_profile: SplitProfile;
  /** The applied profile; "none" when the file stays whole. */
  profile: SplitProfile;
  kept_whole: SplitKeptWhole | null;
  law: string | null;
  court: string | null;
  volume: string | null;
  unit_count: number;
  article_count: number;
  /** Every unit, in document order. */
  units: SplitPreviewUnit[];
}

export interface SplitPreviewResponse {
  sources: SplitPreviewSource[];
  /** True when some units carry only an excerpt of their text. */
  text_budget_exceeded: boolean;
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

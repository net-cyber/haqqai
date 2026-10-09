import type {
  NextMissingIssue,
  SplitIssueKind,
  SplitPathLevel,
  SplitPreviewUnit,
} from "@/lib/fileConnector";

/** Which units the review list shows. */
export type ReviewFilter = "all" | "to_check" | SplitIssueKind;

/** One row of the review outline, in document order. */
export type OutlineEntry =
  | {
      type: "group";
      key: string;
      label: string;
      count: number;
      toCheck: number;
      open: boolean;
      /** False while a filter or search opens every group with a match. */
      collapsible: boolean;
    }
  | { type: "crumb"; key: string; level: SplitPathLevel; label: string }
  | { type: "unit"; unit: SplitPreviewUnit }
  | { type: "gap"; key: string; issue: NextMissingIssue };

export interface SplitReviewCounts {
  all: number;
  /** Flagged units that are not marked checked. */
  toCheck: number;
  flagged: number;
  checked: number;
  /** Units that have each issue kind, checked or not. */
  byKind: Record<SplitIssueKind, number>;
}

export interface OutlineResult {
  entries: OutlineEntry[];
  /** Units that pass the filter or search, collapsed groups included. */
  visibleUnitIds: string[];
}

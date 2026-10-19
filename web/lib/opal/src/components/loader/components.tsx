"use client";

import "@opal/components/loader/styles.css";
import { cn } from "@opal/utils";
import { useOpalStrings } from "@opal/strings";

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

// Marks render in `currentColor`, so color is applied as a text token.
// Default is the neutral `border-02`. Pass `color` to override, or
// `"inherit"` to set no class and let the ambient text color flow through.
type LoaderColor =
  | "inherit"
  | "border-02"
  | "text-02"
  | "text-03"
  | "text-04"
  | "text-05"
  | "status-error-05"
  | "status-success-05"
  | "status-warning-05";

const COLOR_CLASS: Record<LoaderColor, string> = {
  inherit: "",
  "border-02": "text-border-02",
  "text-02": "text-text-02",
  "text-03": "text-text-03",
  "text-04": "text-text-04",
  "text-05": "text-text-05",
  "status-error-05": "text-status-error-05",
  "status-success-05": "text-status-success-05",
  "status-warning-05": "text-status-warning-05",
};

// ---------------------------------------------------------------------------
// OnyxLoader
// ---------------------------------------------------------------------------

interface OnyxLoaderProps {
  /** Size of the animated mark, in pixels. @default 64 */
  size?: number;

  /** Mark color token. @default "border-02" */
  color?: LoaderColor;
}

// Geometry matches the Scovra compass mark in @opal/logos (ring and needle),
// scaled to a 16px box. Stroke is defined here so weight can be tuned: ~2.5px
// at the default 64px, scaling with `size`.
const STROKE_WIDTH = 0.625;

const RING_PATH = "M1.5 8A6.5 6.5 0 1 1 14.5 8A6.5 6.5 0 1 1 1.5 8Z";

const OUTLINE_PATH = RING_PATH;

function svgLayerProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    xmlns: "http://www.w3.org/2000/svg",
  };
}

const MARK_PATHS = [
  RING_PATH,
  "M11.5 4.5L9.15 9.15L6.85 6.85Z",
  "M4.5 11.5L6.85 6.85L9.15 9.15Z",
];

/**
 * Branded loading mark: rotates a full turn while crossfading between the
 * compass ring and the ring with its needle (2s loop), holding the static ring
 * under `prefers-reduced-motion`. Uses `currentColor`, so `color` themes it.
 * For a full-page loading state with a label, use `PageLoader`.
 */
function OnyxLoader({ size = 64, color = "border-02" }: OnyxLoaderProps) {
  const strings = useOpalStrings();
  return (
    <div
      role="status"
      aria-label={strings.loading}
      className={cn("relative shrink-0", COLOR_CLASS[color])}
      style={{ width: size, height: size }}
    >
      <div className="opal-loader-rotator">
        <svg
          {...svgLayerProps(size)}
          className="opal-loader-layer opal-loader-outline"
        >
          <path
            d={OUTLINE_PATH}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <svg
          {...svgLayerProps(size)}
          className="opal-loader-layer opal-loader-mark"
        >
          {MARK_PATHS.map((d) => (
            <path
              key={d}
              d={d}
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

export { OnyxLoader, type OnyxLoaderProps, type LoaderColor };

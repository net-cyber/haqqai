"use client";

import Image from "next/image";
import { StaticImageData } from "next/image";
import { useTranslations } from "next-intl";
import openSourceIcon from "@public/OpenSource.png";
import trelloIcon from "@public/Trello.png";
import serviceNowIcon from "@public/Servicenow.png";
import zAIIcon from "@public/Z_AI.png";

export interface IconProps {
  size?: number;
  className?: string;
}
export interface LogoIconProps extends IconProps {
  src: string | StaticImageData;
}

export const defaultTailwindCSS = "my-auto flex shrink-0 text-default";
export const defaultTailwindCSSBlue = "my-auto flex shrink-0 text-link";

export const LogoIcon = ({
  size = 16,
  className = defaultTailwindCSS,
  src,
}: LogoIconProps) => {
  const t = useTranslations("common.icons");
  return (
    <Image
      style={{ width: `${size}px`, height: `${size}px` }}
      className={`w-[${size}px] h-[${size}px] object-contain ` + className}
      src={src}
      alt={t("logo.alt")}
      width="96"
      height="96"
    />
  );
};

// Helper to create simple icon components from react-icon libraries
export function createIcon(
  IconComponent: React.ComponentType<{ size?: number; className?: string }>
) {
  function IconWrapper({
    size = 16,
    className = defaultTailwindCSS,
  }: IconProps) {
    return <IconComponent size={size} className={className} />;
  }

  IconWrapper.displayName = `Icon(${
    IconComponent.displayName || IconComponent.name || "Component"
  })`;
  return IconWrapper;
}

/**
 * Creates a logo icon component that automatically supports dark mode adaptations.
 *
 * Depending on the options provided, the returned component handles:
 * 1. Light/Dark variants: If both `src` and `darkSrc` are provided, displays the
 *    appropriate image based on the current color theme.
 * 2. Monochromatic inversion: If `monochromatic` is true, applies a CSS color inversion
 *    in dark mode for a monochrome icon appearance.
 * 3. Static icon: If only `src` is provided, renders the image without dark mode adaptation.
 *
 * @param src - The image or SVG source used for the icon (light/default mode).
 * @param options - Optional settings:
 *   - darkSrc: The image or SVG source used specifically for dark mode.
 *   - monochromatic: If true, applies a CSS inversion in dark mode for monochrome logos.
 *   - sizeAdjustment: Number to add to the icon size (e.g., 4 to make icon larger).
 *   - classNameAddition: Additional CSS classes to apply (e.g., '-m-0.5' for margin).
 * @returns A React functional component that accepts {@link IconProps} and renders
 *          the logo with dark mode handling as needed.
 */
const createLogoIcon = (
  src: string | StaticImageData,
  options?: {
    darkSrc?: string | StaticImageData;
    monochromatic?: boolean;
    sizeAdjustment?: number;
    classNameAddition?: string;
  }
) => {
  const {
    darkSrc,
    monochromatic,
    sizeAdjustment = 0,
    classNameAddition = "",
  } = options || {};

  const LogoIconWrapper = ({
    size = 16,
    className = defaultTailwindCSS,
  }: IconProps) => {
    const adjustedSize = size + sizeAdjustment;

    // Build className dynamically (only apply monochromatic if no darkSrc)
    const monochromaticClass = !darkSrc && monochromatic ? "dark:invert" : "";
    const finalClassName = [className, classNameAddition, monochromaticClass]
      .filter(Boolean)
      .join(" ");

    // If darkSrc is provided, use CSS-based dark mode switching
    // This avoids hydration issues and content flashing since next-themes
    // sets the .dark class before React hydrates
    if (darkSrc) {
      return (
        <>
          <LogoIcon
            size={adjustedSize}
            className={`${finalClassName} dark:hidden`}
            src={src}
          />
          <LogoIcon
            size={adjustedSize}
            className={`${finalClassName} hidden dark:block`}
            src={darkSrc}
          />
        </>
      );
    }

    return (
      <LogoIcon size={adjustedSize} className={finalClassName} src={src} />
    );
  };

  LogoIconWrapper.displayName = "LogoIconWrapper";
  return LogoIconWrapper;
};

// ============================================================================
// GENERIC SVG COMPONENTS (sorted alphabetically)
// ============================================================================
export const MacIcon = ({
  size = 16,
  className = "my-auto flex shrink-0 ",
}: IconProps) => {
  return (
    <svg
      style={{ width: `${size}px`, height: `${size}px` }}
      className={`w-[${size}px] h-[${size}px] ` + className}
      xmlns="http://www.w3.org/2000/svg"
      width="200"
      height="200"
      viewBox="0 0 24 24"
    >
      <path
        fill="currentColor"
        d="M6.5 4.5a2 2 0 0 1 2 2v2h-2a2 2 0 1 1 0-4Zm4 4v-2a4 4 0 1 0-4 4h2v3h-2a4 4 0 1 0 4 4v-2h3v2a4 4 0 1 0 4-4h-2v-3h2a4 4 0 1 0-4-4v2h-3Zm0 2h3v3h-3v-3Zm5-2v-2a2 2 0 1 1 2 2h-2Zm0 7h2a2 2 0 1 1-2 2v-2Zm-7 0v2a2 2 0 1 1-2-2h2Z"
      />
    </svg>
  );
};
// Scovra lockup (mark and wordmark) in one color, sized by width.
export const OnyxLogoTypeIcon = ({
  size = 16,
  className = defaultTailwindCSS,
}: IconProps) => {
  const aspectRatio = 263 / 64;
  const height = size / aspectRatio;

  return (
    <svg
      version="1.1"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={height}
      viewBox="0 0 263 64"
      style={{ width: `${size}px`, height: `${height}px` }}
      className={`w-[${size}px] h-[${height}px] ` + className}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M3 32A29 29 0 1 0 61 32A29 29 0 1 0 3 32ZM9 32A23 23 0 1 0 55 32A23 23 0 1 0 9 32Z"
        fill="currentColor"
      />
      <path d="M46 18L36.6 36.6L27.4 27.4Z" fill="currentColor" />
      <path
        d="M18 46L27.4 27.4L36.6 36.6Z"
        fill="currentColor"
        fillOpacity={0.45}
      />
      <path
        d="M28.46 40.08Q28.46 45.4 24.59 48.48Q20.73 51.56 13.89 51.56Q7.28 51.56 2.69 49.32V42.6Q5.21 43.72 8.24 44.64Q11.26 45.57 14.4 45.57Q17.98 45.57 19.66 44.17Q21.34 42.76 21.34 40.47Q21.34 37.95 19.22 36.49Q17.09 35.03 13 33.3Q10.53 32.23 8.29 30.78Q6.05 29.32 4.59 27.08Q3.14 24.84 3.14 21.36Q3.14 16.21 6.75 13.32Q10.36 10.44 16.41 10.44Q19.61 10.44 22.38 11.11Q25.15 11.78 27.96 13.02L25.66 18.79Q23.14 17.72 20.87 17.11Q18.6 16.49 16.19 16.49Q13.28 16.49 11.76 17.81Q10.25 19.12 10.25 21.2Q10.25 22.88 11.09 24Q11.93 25.12 13.7 26.07Q15.46 27.02 18.26 28.25Q21.46 29.66 23.75 31.17Q26.05 32.68 27.25 34.81Q28.46 36.94 28.46 40.08ZM47.62 51.56Q41.06 51.56 37.31 47.81Q33.56 44.05 33.56 35.99Q33.56 30.38 35.43 26.88Q37.31 23.38 40.62 21.73Q43.92 20.08 48.18 20.08Q51.04 20.08 53.28 20.64Q55.52 21.2 57.09 21.98L55.01 27.53Q53.28 26.85 51.54 26.38Q49.8 25.9 48.18 25.9Q40.78 25.9 40.78 35.93Q40.78 40.8 42.66 43.27Q44.54 45.73 48.07 45.73Q50.59 45.73 52.55 45.12Q54.51 44.5 56.3 43.44V49.54Q54.57 50.55 52.58 51.06Q50.59 51.56 47.62 51.56ZM90.53 35.76Q90.53 43.32 86.61 47.44Q82.69 51.56 75.97 51.56Q71.82 51.56 68.57 49.71Q65.32 47.86 63.47 44.33Q61.62 40.8 61.62 35.76Q61.62 28.2 65.52 24.14Q69.41 20.08 76.13 20.08Q80.34 20.08 83.59 21.9Q86.83 23.72 88.68 27.22Q90.53 30.72 90.53 35.76ZM68.85 35.76Q68.85 40.58 70.56 43.21Q72.27 45.85 76.08 45.85Q79.89 45.85 81.6 43.21Q83.31 40.58 83.31 35.76Q83.31 30.94 81.6 28.37Q79.89 25.79 76.02 25.79Q72.27 25.79 70.56 28.37Q68.85 30.94 68.85 35.76ZM104.82 51 93.28 20.64H100.73L106.78 38.17Q107.34 39.8 107.82 41.76Q108.29 43.72 108.4 45.06H108.63Q108.8 43.66 109.3 41.73Q109.8 39.8 110.36 38.17L116.41 20.64H123.87L112.32 51ZM144.31 20.08Q145.04 20.08 145.91 20.13Q146.78 20.19 147.39 20.36L146.78 26.91Q146.22 26.8 145.43 26.71Q144.65 26.63 144.03 26.63Q141.79 26.63 139.83 27.55Q137.87 28.48 136.67 30.41Q135.46 32.34 135.46 35.26V51H128.4V20.64H133.84L134.85 25.9H135.18Q136.53 23.49 138.88 21.78Q141.23 20.08 144.31 20.08ZM165.1 20.08Q170.98 20.08 174.03 22.65Q177.09 25.23 177.09 30.61V51H172.1L170.7 46.8H170.48Q168.52 49.26 166.33 50.41Q164.15 51.56 160.39 51.56Q156.3 51.56 153.61 49.26Q150.92 46.97 150.92 42.15Q150.92 37.44 154.37 35.09Q157.82 32.74 164.82 32.46L170.08 32.29V30.78Q170.08 27.92 168.68 26.66Q167.28 25.4 164.76 25.4Q162.46 25.4 160.36 26.07Q158.26 26.74 156.19 27.64L153.95 22.71Q156.19 21.53 159.08 20.8Q161.96 20.08 165.1 20.08ZM166.39 36.77Q161.74 36.94 159.94 38.37Q158.15 39.8 158.15 42.2Q158.15 44.39 159.41 45.31Q160.67 46.24 162.75 46.24Q165.83 46.24 167.96 44.47Q170.08 42.71 170.08 39.24V36.66Z"
        fill="currentColor"
        transform="translate(80 0)"
      />
    </svg>
  );
};
export const WindowsIcon = ({
  size = 16,
  className = "my-auto flex shrink-0 ",
}: IconProps) => {
  return (
    <svg
      style={{ width: `${size}px`, height: `${size}px` }}
      className={`w-[${size}px] h-[${size}px] ` + className}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width="24"
      height="24"
    >
      <path
        fill="currentColor"
        d="M3 3h8v8H3V3zm10 0h8v8h-8V3zm-10 10h8v8H3v-8zm10 0h8v8h-8v-8z"
      />
    </svg>
  );
};

// ============================================================================
// THIRD-PARTY / COMPANY ICONS (Alphabetically)
// Only icons that don't yet have opal logo equivalents remain here.
// ============================================================================
export const OpenSourceIcon = createLogoIcon(openSourceIcon);
export const ServiceNowIcon = createLogoIcon(serviceNowIcon);
export const TrelloIcon = createLogoIcon(trelloIcon);
export const ZAIIcon = createLogoIcon(zAIIcon);

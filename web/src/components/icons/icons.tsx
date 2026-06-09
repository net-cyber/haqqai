"use client";

import Image from "next/image";
import { StaticImageData } from "next/image";
import googleCloudStorageIcon from "@public/GoogleCloudStorage.png";
import openSourceIcon from "@public/OpenSource.png";
import r2Icon from "@public/r2.png";
import s3Icon from "@public/S3.png";
import boxIcon from "@public/Box.png";
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
}: LogoIconProps) => (
  <Image
    style={{ width: `${size}px`, height: `${size}px` }}
    className={`w-[${size}px] h-[${size}px] object-contain ` + className}
    src={src}
    alt="Logo"
    width="96"
    height="96"
  />
);

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


export const OnyxLogoTypeIcon = ({
  size = 16,
  className = defaultTailwindCSS,
}: IconProps) => {
  const aspectRatio = 900 / 300; // Calculate the aspect ratio of the original SVG
  const height = size / aspectRatio; // Calculate the height based on the aspect ratio

  return (
    <svg
      version="1.1"
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={height}
      viewBox="0 0 900 300"
      style={{ width: `${size}px`, height: `${height}px` }}
      className={`w-[${size}px] h-[${height}px] ` + className}
    >
      {/* Crown pin at top of pillar */}
      <circle cx="135" cy="22" r="14" fill="currentColor" />

      {/* Vertical support pillar */}
      <rect x="129" y="34" width="12" height="238" rx="6" fill="currentColor" />

      {/* Base platform */}
      <rect x="88" y="266" width="94" height="14" rx="7" fill="currentColor" />

      {/* Horizontal balance beam */}
      <rect x="15" y="50" width="240" height="10" rx="5" fill="currentColor" />

      {/* Left hanging chain */}
      <rect x="17" y="60" width="4" height="72" rx="2" fill="currentColor" />

      {/* Right hanging chain */}
      <rect x="249" y="60" width="4" height="72" rx="2" fill="currentColor" />

      {/* Left scale pan */}
      <path
        d="M 0 132 Q 19 164 38 132"
        stroke="currentColor"
        strokeWidth="6"
        fill="none"
        strokeLinecap="round"
      />

      {/* Right scale pan */}
      <path
        d="M 232 132 Q 251 164 270 132"
        stroke="currentColor"
        strokeWidth="6"
        fill="none"
        strokeLinecap="round"
      />

      {/* HaqqAI wordmark */}
      <text
        x="300"
        y="214"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="162"
        fontWeight="bold"
        fill="currentColor"
        letterSpacing="6"
      >
        HaqqAI
      </text>
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
export const BoxIcon = createLogoIcon(boxIcon);
export const GoogleStorageIcon = createLogoIcon(googleCloudStorageIcon, {
  sizeAdjustment: 4,
  classNameAddition: "-m-0.5",
});
export const OpenSourceIcon = createLogoIcon(openSourceIcon);
export const R2Icon = createLogoIcon(r2Icon);
export const S3Icon = createLogoIcon(s3Icon);
export const ServiceNowIcon = createLogoIcon(serviceNowIcon);
export const TrelloIcon = createLogoIcon(trelloIcon);
export const ZAIIcon = createLogoIcon(zAIIcon);

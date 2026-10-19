import SvgOnyxLogo from "@opal/logos/onyx-logo";
import SvgOnyxTyped from "@opal/logos/onyx-typed";
import { cn } from "@opal/utils";

interface OnyxLogoTypedProps {
  size?: number;
  className?: string;
}

// The Scovra mark and wordmark have more side bearing than the Onyx art, so a
// 1/4 ratio keeps the visible gap of the original 5/16 Figma lockup.
const HEIGHT_TO_GAP_RATIO = 1 / 4;

const SvgOnyxLogoTyped = ({ size: height, className }: OnyxLogoTypedProps) => {
  const gap = height != null ? height * HEIGHT_TO_GAP_RATIO : undefined;

  return (
    <div
      className={cn(`flex flex-row items-center`, className)}
      style={{ gap }}
    >
      <SvgOnyxLogo size={height} />
      <SvgOnyxTyped size={height} />
    </div>
  );
};
export default SvgOnyxLogoTyped;

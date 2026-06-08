import type { IconProps } from "@opal/types";
const SvgOnyxTyped = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 200 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <text
      x="0"
      y="48"
      fontFamily="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
      fontSize="44"
      fontWeight="600"
      fill="var(--theme-primary-05)"
      letterSpacing="-1"
    >
      HaqqAI
    </text>
  </svg>
);
export default SvgOnyxTyped;

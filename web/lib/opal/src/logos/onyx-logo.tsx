import type { IconProps } from "@opal/types";
// Scovra mark: a compass ring with a needle that points north-east.
const SvgOnyxLogo = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M3 32A29 29 0 1 0 61 32A29 29 0 1 0 3 32ZM9 32A23 23 0 1 0 55 32A23 23 0 1 0 9 32Z"
      fill="var(--theme-primary-05)"
    />
    <path d="M46 18L36.6 36.6L27.4 27.4Z" fill="var(--theme-primary-05)" />
    <path
      d="M18 46L27.4 27.4L36.6 36.6Z"
      fill="var(--theme-primary-05)"
      fillOpacity={0.45}
    />
  </svg>
);
export default SvgOnyxLogo;

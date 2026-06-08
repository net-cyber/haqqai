import type { IconProps } from "@opal/types";
const SvgOnyxLogo = ({ size, ...props }: IconProps) => (
  <svg
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...props}
  >
    {/* Central pillar */}
    <line x1="32" y1="10" x2="32" y2="54" stroke="var(--theme-primary-05)" strokeWidth="2" strokeLinecap="round"/>
    {/* Base */}
    <line x1="20" y1="54" x2="44" y2="54" stroke="var(--theme-primary-05)" strokeWidth="2" strokeLinecap="round"/>
    {/* Beam */}
    <line x1="10" y1="20" x2="54" y2="20" stroke="var(--theme-primary-05)" strokeWidth="2" strokeLinecap="round"/>
    {/* Top pivot knob */}
    <circle cx="32" cy="10" r="2.5" fill="var(--theme-primary-05)"/>
    {/* Left pan strings */}
    <line x1="10" y1="20" x2="6" y2="38" stroke="var(--theme-primary-05)" strokeWidth="1.2" strokeLinecap="round"/>
    <line x1="10" y1="20" x2="16" y2="38" stroke="var(--theme-primary-05)" strokeWidth="1.2" strokeLinecap="round"/>
    {/* Right pan strings */}
    <line x1="54" y1="20" x2="48" y2="38" stroke="var(--theme-primary-05)" strokeWidth="1.2" strokeLinecap="round"/>
    <line x1="54" y1="20" x2="58" y2="38" stroke="var(--theme-primary-05)" strokeWidth="1.2" strokeLinecap="round"/>
    {/* Left pan */}
    <path d="M4 38 Q11 44 18 38" stroke="var(--theme-primary-05)" strokeWidth="1.5" strokeLinecap="round"/>
    {/* Right pan */}
    <path d="M46 38 Q53 44 60 38" stroke="var(--theme-primary-05)" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);
export default SvgOnyxLogo;
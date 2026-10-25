/*
 * Icon set for the app shell. Hand-written 24x24 outline paths, stroke-only,
 * single family, uniform strokeWidth 1.6. No icon package is installed in this
 * project, so these live here rather than adding a dependency for four glyphs.
 */
type IconProps = { className?: string };

function base(className?: string) {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
    className,
  };
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.2-4.2" />
    </svg>
  );
}

export function GraphIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="9" r="2.5" />
      <circle cx="10" cy="18" r="2.5" />
      <path d="M8.2 7.4 15.9 8.4M7.1 8.4l1.9 7.2M16.6 11.1l-4.9 5.2" />
    </svg>
  );
}

export function MetricsIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8 16v-4M12.5 16V7M17 16v-6" />
    </svg>
  );
}

export function HistoryIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M3.6 12a8.4 8.4 0 1 0 2.6-6.1" />
      <path d="M3.5 5v4h4" />
      <path d="M12 8v4.4l3 1.8" />
    </svg>
  );
}

export function PanelToggleIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
      <path d="M9.5 4.5v15" />
    </svg>
  );
}

export function ChevronDownIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="m6 9.5 6 6 6-6" />
    </svg>
  );
}

export function SlidersIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M5 7h9M18 7h1M5 12h3M12 12h7M5 17h9M18 17h1" />
      <circle cx="16" cy="7" r="1.8" />
      <circle cx="10" cy="12" r="1.8" />
      <circle cx="16" cy="17" r="1.8" />
    </svg>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <svg {...base(className)}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

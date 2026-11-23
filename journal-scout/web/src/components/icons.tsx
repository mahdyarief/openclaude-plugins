import {
  BarChart3,
  BookOpen,
  ChevronDown,
  FileDown,
  History,
  Mountain,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

type IconProps = { className?: string };

export function SearchIcon({ className }: IconProps) {
  return <Search className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function GraphIcon({ className }: IconProps) {
  return <Network className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function LandscapeIcon({ className }: IconProps) {
  return <Mountain className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function MetricsIcon({ className }: IconProps) {
  return <BarChart3 className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function HistoryIcon({ className }: IconProps) {
  return <History className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function PanelToggleIcon({
  className,
  open,
}: IconProps & { open?: boolean }) {
  const Icon = open ? PanelLeftClose : PanelLeftOpen;
  return <Icon className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function ChevronDownIcon({ className }: IconProps) {
  return <ChevronDown className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function DocsIcon({ className }: IconProps) {
  return <BookOpen className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function SlidersIcon({ className }: IconProps) {
  return (
    <SlidersHorizontal className={className} strokeWidth={1.6} aria-hidden="true" />
  );
}

export function CloseIcon({ className }: IconProps) {
  return <X className={className} strokeWidth={1.6} aria-hidden="true" />;
}

export function PdfIcon({ className }: IconProps) {
  return <FileDown className={className} strokeWidth={1.6} aria-hidden="true" />;
}

/*
 * Reusable UI components. Single source of truth for markup + variants.
 *
 * Radius scale (documented, three tiers only):
 *   - containers / panels: 8px  (rounded-lg)
 *   - controls (button, input, select): 6px (rounded-md)
 *   - inline micro-actions and chips: 4px (rounded)
 *
 * Contrast floor: secondary text is slate-400 (7.3:1 on the canvas token).
 * slate-500 never carries text. Interactive borders use slate-500 (3.77:1)
 * so they clear WCAG 1.4.11 non-text contrast.
 */
import type { ComponentProps, ReactNode } from "react";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* --------------------------------------------------------------- Spinner */

type SpinnerSize = "xs" | "sm" | "md";

const SPINNER_SIZES: Record<SpinnerSize, string> = {
  xs: "h-3 w-3 border-[1.5px]",
  sm: "h-3.5 w-3.5 border-2",
  md: "h-4 w-4 border-2",
};

export function Spinner({
  size = "sm",
  className,
}: {
  size?: SpinnerSize;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "spinner inline-block shrink-0 rounded-full border-current border-t-transparent",
        SPINNER_SIZES[size],
        className,
      )}
      aria-hidden="true"
    />
  );
}

export function LoadingLine({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      role="status"
      className={cn("m-0 flex items-center gap-2 text-[13px] text-slate-400", className)}
    >
      <Spinner />
      {children}
    </p>
  );
}

/* ---------------------------------------------------------------- Button */

type ButtonVariant = "primary" | "ghost" | "accent" | "danger";
type ButtonSize = "md" | "sm";

const BUTTON_BASE =
  "touch-target inline-flex shrink-0 items-center justify-center gap-1.5 font-semibold no-underline transition-colors active:translate-y-px disabled:cursor-not-allowed";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-sky-400 text-slate-950 hover:bg-sky-300 disabled:opacity-50",
  ghost:
    "border border-slate-500 text-slate-300 hover:bg-slate-800/60 hover:text-slate-100 disabled:opacity-50",
  accent:
    "border border-sky-500/50 text-sky-300 hover:bg-sky-500/15 disabled:opacity-60",
  danger:
    "border border-rose-500/50 text-rose-300 hover:bg-rose-500/15 hover:text-rose-200 disabled:opacity-60",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  md: "h-8 rounded-md px-3 text-[13px]",
  sm: "rounded px-1.5 py-0.5 text-[11px] font-normal",
};

export function buttonClass(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string,
): string {
  return cn(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], className);
}

export interface ButtonProps extends ComponentProps<"button"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClass(variant, size, className)}
      {...props}
    />
  );
}

export interface AnchorButtonProps extends ComponentProps<"a"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function AnchorButton({
  variant = "ghost",
  size = "md",
  className,
  ...props
}: AnchorButtonProps) {
  return <a className={buttonClass(variant, size, className)} {...props} />;
}

/* ----------------------------------------------------------------- Input */

export interface InputProps extends ComponentProps<"input"> {
  controlSize?: "md" | "sm";
}

const INPUT_BASE =
  "rounded-md border border-slate-500 bg-slate-950/60 text-[13px] text-slate-100 outline-none transition-colors placeholder:text-slate-400 hover:border-slate-500 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/25";

export function Input({ controlSize = "md", className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        INPUT_BASE,
        controlSize === "md" ? "h-9 px-3" : "h-8 px-2.5",
        className,
      )}
      {...props}
    />
  );
}

export interface SelectProps extends ComponentProps<"select"> {
  controlSize?: "md" | "sm";
}

export function Select({ controlSize = "sm", className, ...props }: SelectProps) {
  return (
    <select
      className={cn(
        INPUT_BASE,
        controlSize === "md" ? "h-9 px-3" : "h-8 px-2.5",
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------- Layout surfaces */

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-lg border border-slate-800 bg-slate-900/40", className)}
      {...props}
    />
  );
}

export function Panel({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("rounded-lg border border-slate-800 bg-slate-950/50", className)}
      {...props}
    />
  );
}

export function Chip({ className, ...props }: ComponentProps<"span">) {
  return (
    <span
      className={cn(
        "rounded border border-slate-700 bg-slate-800/50 px-1.5 py-0.5 text-[11px] leading-4 text-slate-300",
        className,
      )}
      {...props}
    />
  );
}

/* -------------------------------------------------------------- Page head */

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, className }: PageHeaderProps) {
  return (
    <section className={cn("space-y-1.5", className)}>
      <h1 className="m-0 text-xl font-semibold tracking-tight text-slate-50">{title}</h1>
      {description && (
        <p className="m-0 text-[13px] leading-relaxed text-slate-400">{description}</p>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- Alerts */

type AlertTone = "error" | "warn" | "ok";

const ALERT_TONES: Record<AlertTone, string> = {
  error: "border-red-500/40 bg-red-500/10 text-red-200",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
};

export interface AlertProps extends ComponentProps<"div"> {
  tone?: AlertTone;
}

export function Alert({ tone = "error", className, ...props }: AlertProps) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "rounded-lg border px-3 py-2 text-[13px]",
        ALERT_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

/* ----------------------------------------------------------------- Field */

export interface FieldProps {
  label: string;
  hint?: string;
  className?: string;
  children: ReactNode;
}

export function Field({ label, hint, className, children }: FieldProps) {
  return (
    <label className={cn("flex flex-col gap-1 text-[11px] text-slate-400", className)}>
      {label}
      {children}
      {hint && <span className="text-[11px] text-slate-400">{hint}</span>}
    </label>
  );
}

/* ------------------------------------------------------------ Navigation */

export const LINK_CLASS =
  "text-sky-400 underline-offset-2 no-underline hover:text-sky-300 hover:underline";

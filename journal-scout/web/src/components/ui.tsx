/*
 * shadcn/ui-based component layer.
 *
 * Every primitive below is a thin, themed wrapper over a shadcn/Radix
 * implementation: Button/Input/Label use the shadcn slot + cva pattern,
 * Select is Radix Select, and the feedback surfaces (Alert, Badge, Card,
 * Separator) follow shadcn structure. The public API of the previous
 * hand-rolled components is preserved so existing call sites keep working.
 */
import type { ComponentProps, ReactNode } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import {
  Select as ShadcnSelect,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./select";

export { cn };
export { ToggleGroup, ToggleGroupItem } from "./toggle-group";
export { Checkbox, Label } from "./checkbox";

/* --------------------------------------------------------------- Spinner */

type SpinnerSize = "xs" | "sm" | "md";

const SPINNER_SIZES: Record<SpinnerSize, string> = {
  xs: "h-3 w-3",
  sm: "h-3.5 w-3.5",
  md: "h-4 w-4",
};

export function Spinner({
  size = "sm",
  className,
}: {
  size?: SpinnerSize;
  className?: string;
}) {
  return (
    <Loader2
      className={cn("shrink-0 animate-spin", SPINNER_SIZES[size], className)}
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
      className={cn(
        "m-0 flex items-center gap-2 text-[13px] text-slate-400",
        className,
      )}
    >
      <Spinner />
      {children}
    </p>
  );
}

/* ---------------------------------------------------------------- Button */

const buttonVariants = cva(
  "touch-target inline-flex shrink-0 items-center justify-center gap-1.5 font-semibold no-underline transition-colors active:translate-y-px disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-sky-400 text-slate-950 hover:bg-sky-300",
        ghost:
          "border border-slate-500 text-slate-300 hover:bg-slate-800/60 hover:text-slate-100",
        accent:
          "border border-sky-500/50 text-sky-300 hover:bg-sky-500/15",
        danger:
          "border border-rose-500/50 text-rose-300 hover:bg-rose-500/15 hover:text-rose-200",
        default: "bg-sky-400 text-slate-950 hover:bg-sky-300",
        secondary:
          "border border-slate-500 bg-slate-900/60 text-slate-200 hover:bg-slate-800",
        outline:
          "border border-slate-500 bg-transparent text-slate-200 hover:bg-slate-800/60",
        link: "text-sky-400 underline-offset-2 hover:underline",
      },
      size: {
        md: "h-8 rounded-md px-3 text-[13px]",
        sm: "rounded px-1.5 py-0.5 text-[11px] font-normal",
        default: "h-8 rounded-md px-3 text-[13px]",
        icon: "h-8 w-8 rounded-md",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export function buttonClass(
  variant: "primary" | "ghost" | "accent" | "danger" | "default" | "secondary" | "outline" | "link" = "primary",
  size: "md" | "sm" | "default" | "icon" = "md",
  className?: string,
): string {
  return cn(buttonVariants({ variant, size }), className);
}

export interface ButtonProps
  extends ComponentProps<"button">,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      type={asChild ? undefined : type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export interface AnchorButtonProps
  extends ComponentProps<"a">,
    VariantProps<typeof buttonVariants> {}

export function AnchorButton({
  variant = "ghost",
  size = "md",
  className,
  ...props
}: AnchorButtonProps) {
  return <a className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

/* ------------------------------------------------------------ Input / Label */

const inputVariants = cva(
  "rounded-md border border-slate-500 bg-slate-950/60 text-[13px] text-slate-100 outline-none transition-colors placeholder:text-slate-400 file:border-0 file:bg-transparent file:text-[13px] file:font-medium hover:border-slate-500 focus-visible:border-sky-400 focus-visible:ring-2 focus-visible:ring-sky-400/25 disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      controlSize: {
        md: "h-9 px-3",
        sm: "h-8 px-2.5",
      },
    },
    defaultVariants: {
      controlSize: "md",
    },
  },
);

export interface InputProps
  extends ComponentProps<"input">,
    VariantProps<typeof inputVariants> {}

export function Input({ controlSize = "md", className, ...props }: InputProps) {
  return (
    <input className={cn(inputVariants({ controlSize }), className)} {...props} />
  );
}

/* ---------------------------------------------------------------- Select */

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

type SelectControlSize = "md" | "sm";

export interface SelectProps {
  value?: string | number;
  onChange?: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  disabled?: boolean;
  name?: string;
  className?: string;
  "aria-label"?: string;
  placeholder?: string;
  controlSize?: SelectControlSize;
  options?: SelectOption[];
  children?: ReactNode;
}

/**
 * Radix Select wrapper.
 *
 * Call sites that pass `<option>` children keep working: options are read from
 * the React children. Call sites can also pass an explicit `options` array.
 */
export function Select({
  controlSize = "sm",
  className,
  value,
  onChange,
  disabled,
  name,
  options,
  children,
  placeholder,
  "aria-label": ariaLabel,
}: SelectProps) {
  const parsed: SelectOption[] =
    options ??
    extractOptions(children);

  return (
    <ShadcnSelect
      value={value === undefined || value === null ? undefined : String(value)}
      onValueChange={(next) => {
        onChange?.({
          target: { value: next },
        } as unknown as React.ChangeEvent<HTMLSelectElement>);
      }}
      disabled={disabled}
      name={name}
    >
      <SelectTrigger
        aria-label={ariaLabel}
        className={cn(
          controlSize === "md" ? "h-9 text-[13px]" : "h-8 text-[11px]",
          className,
        )}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {parsed.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            disabled={option.disabled}
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </ShadcnSelect>
  );
}

function extractOptions(children: ReactNode): SelectOption[] {
  const result: SelectOption[] = [];
  const visit = (nodes: ReactNode) => {
    if (Array.isArray(nodes)) {
      nodes.forEach(visit);
      return;
    }
    if (
      nodes &&
      typeof nodes === "object" &&
      "props" in nodes &&
      (nodes as { type?: unknown }).type === "option"
    ) {
      const props = (nodes as { props: { value?: string; children?: ReactNode; disabled?: boolean } }).props;
      result.push({
        value: String(props.value ?? ""),
        label: typeof props.children === "string" ? props.children : String(props.value ?? ""),
        disabled: props.disabled,
      });
      return;
    }
  };
  visit(children);
  return result;
}

/* ------------------------------------------------------- Layout surfaces */

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "rounded-lg border border-slate-800 bg-slate-900/40 text-slate-100",
        className,
      )}
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

const badgeVariants = cva(
  "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] leading-4",
  {
    variants: {
      variant: {
        default: "border-slate-700 bg-slate-800/50 text-slate-300",
        secondary: "border-slate-700 bg-slate-800/70 text-slate-200",
        outline: "border-slate-600 bg-transparent text-slate-300",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface ChipProps
  extends ComponentProps<"span">,
    VariantProps<typeof badgeVariants> {}

export function Chip({ className, variant, ...props }: ChipProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
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
      <h1 className="m-0 text-xl font-semibold tracking-tight text-slate-50">
        {title}
      </h1>
      {description && (
        <p className="m-0 text-[13px] leading-relaxed text-slate-400">{description}</p>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- Alerts */

type AlertTone = "error" | "warn" | "ok" | "info";

const ALERT_TONES: Record<AlertTone, string> = {
  error: "border-red-500/40 bg-red-500/10 text-red-200",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  info: "border-sky-500/40 bg-sky-500/10 text-sky-200",
};

export interface AlertProps extends ComponentProps<"div"> {
  tone?: AlertTone;
}

export function Alert({ tone = "error", className, ...props }: AlertProps) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "relative w-full rounded-lg border px-3 py-2 text-[13px]",
        ALERT_TONES[tone],
        className,
      )}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("mb-0.5 font-semibold", className)} {...props} />;
}

export function AlertDescription({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("text-[12.5px] leading-relaxed", className)} {...props} />;
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

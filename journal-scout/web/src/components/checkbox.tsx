import * as React from "react";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as LabelPrimitive from "@radix-ui/react-label";
import { Check } from "lucide-react";
import { cn } from "../lib/utils";

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer h-3.5 w-3.5 shrink-0 rounded-sm border border-slate-500 bg-slate-950/60 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-sky-400 data-[state=checked]:bg-sky-400 data-[state=checked]:text-slate-950",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center text-current">
      <Check className="h-3 w-3" strokeWidth={2.5} />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-[11px] font-medium text-slate-300", className)}
    {...props}
  />
));
Label.displayName = LabelPrimitive.Root.displayName;

export { Checkbox, Label };

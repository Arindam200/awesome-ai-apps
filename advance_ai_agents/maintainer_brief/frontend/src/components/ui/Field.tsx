import type { ComponentProps, ReactNode } from "react";

const inputBase =
  "w-full rounded-[6px] border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15";

export function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
      {children}
    </label>
  );
}

export function Input({ className = "", ...rest }: ComponentProps<"input">) {
  return <input className={`${inputBase} ${className}`} {...rest} />;
}

export function Textarea({ className = "", ...rest }: ComponentProps<"textarea">) {
  return <textarea className={`${inputBase} resize-y ${className}`} {...rest} />;
}

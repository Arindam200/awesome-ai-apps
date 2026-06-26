import type { ReactNode } from "react";

/** Panel with corner-bracket ticks. Optional mono label + traffic-light dots header. */
export function Frame({
  children,
  label,
  dots = false,
  className = "",
}: {
  children: ReactNode;
  label?: string;
  dots?: boolean;
  className?: string;
}) {
  return (
    <div className={`frame ${className}`}>
      <span className="br" />
      {(label || dots) && (
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          {dots ? (
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
              <span className="h-2.5 w-2.5 rounded-full bg-line-strong" />
            </div>
          ) : (
            <span />
          )}
          {label && (
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-faint">{label}</span>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

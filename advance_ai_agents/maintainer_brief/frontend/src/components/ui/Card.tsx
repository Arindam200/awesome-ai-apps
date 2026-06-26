import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  /** subtle blue sheen at the bottom (feature-card look) */
  sheen?: boolean;
};

export function Card({ children, className = "", hover = false, sheen = false }: Props) {
  return (
    <div
      className={`relative overflow-hidden rounded-[6px] border border-line bg-surface ${
        hover ? "transition-all hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[0_8px_24px_-12px_rgba(43,41,38,0.15)]" : ""
      } ${className}`}
    >
      {children}
      {sheen && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-primary-soft/60 to-transparent" />
      )}
    </div>
  );
}

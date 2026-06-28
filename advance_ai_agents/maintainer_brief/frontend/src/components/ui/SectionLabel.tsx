import type { LucideIcon } from "lucide-react";

type Props = {
  label: string;
  index?: number;
  total?: number;
  icon?: LucideIcon;
  className?: string;
};

export function SectionLabel({ label, index, total, icon: Icon, className = "" }: Props) {
  return (
    <div
      className={`flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-faint ${className}`}
    >
      {Icon ? <Icon size={13} strokeWidth={2} className="text-primary" /> : <span className="text-primary">›</span>}
      <span className="whitespace-nowrap">{label}</span>
      <span className="h-px flex-1 bg-line" />
      {index != null && (
        <span className="whitespace-nowrap">
          [{String(index).padStart(2, "0")}
          {total != null ? `/${String(total).padStart(2, "0")}` : ""}]
        </span>
      )}
    </div>
  );
}

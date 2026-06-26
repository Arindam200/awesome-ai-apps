import type { ReactNode } from "react";

type Tone = "blue" | "gold" | "danger" | "success" | "neutral";

const tones: Record<Tone, string> = {
  blue: "bg-primary-soft text-primary",
  gold: "bg-gold-soft text-gold",
  danger: "bg-danger-soft text-danger",
  success: "bg-success-soft text-success",
  neutral: "bg-surface-2 text-muted",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[4px] px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em] ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Map an urgency/severity level to a tone. */
export function levelTone(level?: string): Tone {
  const l = (level ?? "").toLowerCase();
  if (["critical", "high"].includes(l)) return "danger";
  if (["medium", "moderate"].includes(l)) return "gold";
  if (["low", "info"].includes(l)) return "neutral";
  return "neutral";
}

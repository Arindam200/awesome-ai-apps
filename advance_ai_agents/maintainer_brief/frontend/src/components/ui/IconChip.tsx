import type { LucideIcon } from "lucide-react";

type Tone = "blue" | "gold" | "soft";
type Size = "sm" | "md";

const tones: Record<Tone, string> = {
  blue: "bg-primary text-white",
  gold: "bg-gold text-white",
  soft: "bg-primary-soft text-primary",
};

export function IconChip({
  icon: Icon,
  tone = "blue",
  size = "md",
}: {
  icon: LucideIcon;
  tone?: Tone;
  size?: Size;
}) {
  const dim = size === "sm" ? "h-8 w-8" : "h-10 w-10";
  return (
    <span className={`grid ${dim} shrink-0 place-items-center rounded-[6px] ${tones[tone]}`}>
      <Icon size={size === "sm" ? 15 : 18} strokeWidth={2} />
    </span>
  );
}

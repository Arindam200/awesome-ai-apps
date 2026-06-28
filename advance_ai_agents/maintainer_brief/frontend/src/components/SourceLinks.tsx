import Link from "next/link";
import { Quote } from "lucide-react";

export default function SourceLinks({ ids }: { ids: number[] }) {
  if (!ids?.length) return null;
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {ids.slice(0, 4).map((id) => (
        <Link
          key={id}
          href={`/citations/${id}`}
          className="inline-flex items-center gap-1 rounded-[4px] border border-line bg-surface px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted transition-colors hover:border-primary hover:text-primary"
        >
          <Quote size={10} strokeWidth={2.5} />
          source
        </Link>
      ))}
    </span>
  );
}

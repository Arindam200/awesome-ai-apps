import Link from "next/link";

export default function SourceLinks({ ids }: { ids: number[] }) {
  if (!ids?.length) return null;
  return (
    <span className="inline-flex flex-wrap gap-2">
      {ids.slice(0, 4).map((id) => (
        <Link
          key={id}
          href={`/citations/${id}`}
          className="rounded-sm bg-accent-soft px-2 py-0.5 text-[11px] font-bold text-accent hover:bg-accent hover:text-white"
        >
          View source ↗
        </Link>
      ))}
    </span>
  );
}

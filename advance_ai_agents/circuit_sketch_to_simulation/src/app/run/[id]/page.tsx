import { notFound } from "next/navigation";
import { RunView } from "@/components/RunView";
import { loadRun } from "@/lib/runs";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = /^[a-z0-9-]+$/.test(id) ? await loadRun(id) : null;
  if (!run) notFound();
  return <RunView initial={run} />;
}

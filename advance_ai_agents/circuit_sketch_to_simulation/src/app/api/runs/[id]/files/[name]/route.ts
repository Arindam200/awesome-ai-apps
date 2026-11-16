import { readRunFile } from "@/lib/runs";

export const runtime = "nodejs";

// Generated HTML is only ever served as plain text: it runs inside a sandboxed iframe, never on this origin.
const TYPES: Record<string, string> = { jpg: "image/jpeg", png: "image/png", html: "text/plain; charset=utf-8" };

export async function GET(_req: Request, ctx: { params: Promise<{ id: string; name: string }> }) {
  const { id, name } = await ctx.params;
  const type = TYPES[name.split(".").pop() ?? ""];
  if (!type) return new Response("Not found", { status: 404 });
  try {
    const body = await readRunFile(id, name);
    return new Response(new Uint8Array(body), { headers: { "Content-Type": type, "Cache-Control": "private, max-age=3600" } });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}

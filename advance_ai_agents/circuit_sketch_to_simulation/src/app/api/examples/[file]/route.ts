import { exampleImage } from "@/lib/examples";

export const runtime = "nodejs";

const TYPES: Record<string, string> = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp" };

export async function GET(_req: Request, ctx: { params: Promise<{ file: string }> }) {
  const { file } = await ctx.params;
  const type = TYPES[file.split(".").pop()?.toLowerCase() ?? ""];
  if (!type) return new Response("Not found", { status: 404 });
  try {
    return new Response(new Uint8Array(await exampleImage(file)), { headers: { "Content-Type": type, "Cache-Control": "public, max-age=86400" } });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}

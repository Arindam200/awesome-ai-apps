import { NextRequest, NextResponse } from "next/server";
import { createVeltUserToken, veltServerConfig } from "@/lib/velt";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const config = veltServerConfig();
  if (!config.configured) {
    return NextResponse.json({ error: "Velt server auth is not configured." }, { status: 503 });
  }

  const body = (await request.json().catch(() => ({}))) as {
    userId?: string;
    organizationId?: string;
    email?: string;
    name?: string;
  };
  const userId = body.userId?.trim();
  const organizationId = body.organizationId?.trim() || config.organizationId;

  if (!userId || !organizationId) {
    return NextResponse.json({ error: "userId and organizationId are required." }, { status: 400 });
  }

  try {
    const token = await createVeltUserToken({
      userId,
      organizationId,
      email: body.email,
      name: body.name
    });
    return NextResponse.json({ token });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Velt token generation failed." },
      { status: 502 }
    );
  }
}

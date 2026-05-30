import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

interface RouteParams {
  params: Promise<{
    sessionId: string;
    runId: string;
  }>;
}

export async function POST(
  _req: NextRequest,
  { params }: RouteParams
): Promise<NextResponse> {
  const { sessionId, runId } = await params;

  try {
    const res = await fetch(
      `${BACKEND_URL}/sessions/${sessionId}/manual-checkpoints/${runId}/resume`,
      { method: "POST" }
    );

    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend error: ${res.status}` },
        { status: res.status }
      );
    }

    return NextResponse.json({ resumed: true, runId });
  } catch (err) {
    console.error("Failed to resume manual checkpoint:", err);
    return NextResponse.json(
      { error: "백엔드 서버에 연결할 수 없습니다." },
      { status: 500 }
    );
  }
}

import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(): Promise<NextResponse> {
  try {
    const res = await fetch(`${BACKEND_URL}/sessions`, { method: "POST" });

    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend error: ${res.status}` },
        { status: 500 }
      );
    }

    const data = (await res.json()) as { data: { id: string } };
    return NextResponse.json({ sessionId: data.data.id });
  } catch (err) {
    console.error("Failed to create session:", err);
    return NextResponse.json(
      { error: "백엔드 서버에 연결할 수 없습니다." },
      { status: 500 }
    );
  }
}

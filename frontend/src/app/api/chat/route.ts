import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

interface ChatStreamBody {
  sessionId: string;
  content: string;
  selectedOrder?: {
    menuName: string;
    menuCategory: string;
    options: string[];
    optionDetails?: Array<{
      groupName: string;
      optionName: string;
      addPrice: number;
      required: boolean;
    }>;
    orderType: "delivery" | "pickup";
  } | null;
}

export async function POST(req: NextRequest): Promise<Response> {
  let body: ChatStreamBody;
  try {
    body = (await req.json()) as ChatStreamBody;
  } catch {
    return new Response(JSON.stringify({ error: "Invalid request body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { sessionId, content, selectedOrder } = body;

  if (!sessionId || !content?.trim()) {
    return new Response(
      JSON.stringify({ error: "sessionId and content are required" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(
      `${BACKEND_URL}/sessions/${sessionId}/responses/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: {
            type: "text",
            content,
            selected_order: selectedOrder
              ? {
                  menu_name: selectedOrder.menuName,
                  menu_category: selectedOrder.menuCategory,
                  options: selectedOrder.options,
                  option_details: selectedOrder.optionDetails?.map((option) => ({
                    group_name: option.groupName,
                    option_name: option.optionName,
                    add_price: option.addPrice,
                    required: option.required,
                  })) ?? [],
                  order_type: selectedOrder.orderType,
                }
              : null,
          },
        }),
      }
    );
  } catch (err) {
    console.error("Backend connection error:", err);
    return new Response(
      JSON.stringify({ error: "백엔드 서버에 연결할 수 없습니다." }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  if (!backendRes.ok) {
    const errorText = await backendRes.text();
    console.error(`Backend error ${backendRes.status}:`, errorText);
    return new Response(
      JSON.stringify({ error: `Backend responded with ${backendRes.status}` }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  // 백엔드 SSE 스트림을 클라이언트로 그대로 파이프
  return new Response(backendRes.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}

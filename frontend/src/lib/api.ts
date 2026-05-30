import type {
  ManualCheckpoint,
  Message,
  MenuCard,
  OrderStatus,
  SelectedOrder,
} from "@/types/chat";

// ── 백엔드 SSE 메시지 내부 타입 ───────────────────────────────────────────

interface BackendMessage {
  id: string;
  role: "user" | "assistant";
  type: "text" | "menu_cards" | "clarification" | "order_status";
  content: string | null;
  items: Array<BackendMenuItem | BackendOrderStatus> | null;
  created_at: string;
}

interface BackendMenuItem {
  name: string;
  category: string;
  price: number;
  description: string;
  allergy?: string;
  nutrition?: string;
  options?: string;
  imageURL?: string;
  recommendation_reason?: string;
  recommendation_score?: number;
  matched_criteria?: string;
}

interface BackendOrderStatus {
  status?: string;
  message?: string;
  menu_name?: string;
  expected_options?: string[];
  selected_options?: string[];
  missing_options?: string[];
  order_type?: "delivery" | "pickup" | "";
  current_url?: string;
  next_action?: string;
}

interface BackendManualCheckpoint {
  run_id?: string;
  message?: string;
  created_at?: string;
}

// ── 변환 헬퍼 ────────────────────────────────────────────────────────────────

function toMessage(msg: BackendMessage): Message {
  const timestamp = new Date(msg.created_at);

  if (msg.type === "menu_cards") {
    const cards: MenuCard[] = ((msg.items ?? []) as BackendMenuItem[]).map((item) => ({
      name: item.name,
      category: item.category,
      price: item.price,
      description: item.description,
      allergy: item.allergy,
      nutrition: item.nutrition,
      options: item.options,
      imageURL: item.imageURL,
      recommendationReason: item.recommendation_reason,
      recommendationScore: item.recommendation_score,
      matchedCriteria: item.matched_criteria,
    }));
    return { id: msg.id, role: "assistant", type: "menu_cards", cards, timestamp };
  }

  if (msg.type === "clarification") {
    return {
      id: msg.id,
      role: "assistant",
      type: "clarification",
      content: msg.content ?? "",
      timestamp,
    };
  }

  if (msg.type === "order_status") {
    const rawOrder = (msg.items?.[0] ?? {}) as BackendOrderStatus;
    const order: OrderStatus = {
      status: rawOrder.status ?? "cart_ready",
      message: rawOrder.message ?? msg.content ?? "",
      menuName: rawOrder.menu_name ?? "",
      expectedOptions: rawOrder.expected_options ?? [],
      selectedOptions: rawOrder.selected_options ?? [],
      missingOptions: rawOrder.missing_options ?? [],
      orderType: rawOrder.order_type ?? "",
      currentUrl: rawOrder.current_url ?? "",
      nextAction: rawOrder.next_action ?? "",
    };

    return { id: msg.id, role: "assistant", type: "order_status", order, timestamp };
  }

  return {
    id: msg.id,
    role: "assistant",
    type: "text",
    content: msg.content ?? "",
    timestamp,
  };
}

// ── 공개 API ─────────────────────────────────────────────────────────────────

export async function createSession(): Promise<string> {
  const res = await fetch("/api/sessions", { method: "POST" });
  if (!res.ok) throw new Error(`세션 생성 실패: ${res.status}`);
  const data = (await res.json()) as { sessionId: string };
  return data.sessionId;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onManualCheckpoint: (checkpoint: ManualCheckpoint) => void;
  onMessage: (message: Message) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

export async function streamMessage(
  sessionId: string,
  content: string,
  selectedOrder: SelectedOrder | null,
  callbacks: StreamCallbacks
): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, content, selectedOrder }),
    });
  } catch {
    callbacks.onError(new Error("네트워크 오류가 발생했습니다."));
    return;
  }

  if (!res.ok) {
    callbacks.onError(new Error(`서버 오류: ${res.status}`));
    return;
  }

  if (!res.body) {
    callbacks.onError(new Error("스트림을 읽을 수 없습니다."));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE 이벤트는 "\n\n"으로 구분됨
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6);
        if (!raw) continue;

        try {
          const event = JSON.parse(raw) as {
            event: string;
            token?: string;
            checkpoint?: BackendManualCheckpoint;
            message?: BackendMessage;
          };

          if (event.event === "token" && event.token) {
            callbacks.onToken(event.token);
          } else if (event.event === "manual_checkpoint" && event.checkpoint) {
            callbacks.onManualCheckpoint({
              runId: event.checkpoint.run_id ?? "",
              message: event.checkpoint.message ?? "",
              createdAt: event.checkpoint.created_at
                ? new Date(event.checkpoint.created_at)
                : undefined,
            });
          } else if (event.event === "message" && event.message) {
            callbacks.onMessage(toMessage(event.message));
          } else if (event.event === "done") {
            callbacks.onDone();
          }
        } catch {
          // JSON parse 실패는 무시
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function resumeManualCheckpoint(
  sessionId: string,
  runId: string
): Promise<void> {
  const res = await fetch(
    `/api/sessions/${sessionId}/manual-checkpoints/${runId}/resume`,
    { method: "POST" }
  );

  if (!res.ok) {
    throw new Error(`체크포인트 재개 실패: ${res.status}`);
  }
}

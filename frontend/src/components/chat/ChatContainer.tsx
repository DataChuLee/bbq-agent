"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ManualCheckpoint, Message, SelectedOrder } from "@/types/chat";
import { createSession, resumeManualCheckpoint, streamMessage } from "@/lib/api";
import { MessageList } from "./MessageList";
import { InputBar } from "./InputBar";

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [currentIntent, setCurrentIntent] = useState<string | null>(null);
  const [manualCheckpoint, setManualCheckpoint] = useState<ManualCheckpoint | null>(null);
  const [isResumingCheckpoint, setIsResumingCheckpoint] = useState(false);
  const [sessionError, setSessionError] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    createSession()
      .then((id) => {
        sessionIdRef.current = id;
      })
      .catch((err) => {
        console.error("세션 생성 실패:", err);
        setSessionError(true);
      });
  }, []);

  function handleRetry() {
    setSessionError(false);
    createSession()
      .then((id) => {
        sessionIdRef.current = id;
      })
      .catch(() => setSessionError(true));
  }

  async function handleSend(query: string, selectedOrder: SelectedOrder | null = null) {
    if (!sessionIdRef.current) return;

    const userMessage: Message = {
      id: generateId(),
      role: "user",
      type: "text",
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setStreamingContent("");
    setCurrentIntent(null);

    await streamMessage(sessionIdRef.current, query, selectedOrder, {
      onIntent: (intent) => {
        setCurrentIntent(intent);
      },
      onToken: (token) => {
        setStreamingContent((prev) => (prev ?? "") + token);
      },
      onManualCheckpoint: (checkpoint) => {
        setStreamingContent(null);
        setManualCheckpoint(checkpoint);
        setIsResumingCheckpoint(false);
      },
      onMessage: (msg) => {
        setStreamingContent(null);
        setManualCheckpoint(null);
        setMessages((prev) => [...prev, msg]);
      },
      onDone: () => {
        setIsLoading(false);
        setStreamingContent(null);
        setCurrentIntent(null);
        setManualCheckpoint(null);
        setIsResumingCheckpoint(false);
      },
      onError: (err) => {
        console.error("스트리밍 오류:", err);
        setStreamingContent(null);
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "assistant",
            type: "text",
            content: "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            timestamp: new Date(),
          },
        ]);
        setIsLoading(false);
        setCurrentIntent(null);
        setManualCheckpoint(null);
        setIsResumingCheckpoint(false);
      },
    });
  }

  async function handleResumeCheckpoint() {
    if (!sessionIdRef.current || !manualCheckpoint || isResumingCheckpoint) return;

    setIsResumingCheckpoint(true);
    try {
      await resumeManualCheckpoint(sessionIdRef.current, manualCheckpoint.runId);
      setManualCheckpoint(null);
      setStreamingContent("");
    } catch (err) {
      console.error("체크포인트 재개 실패:", err);
      setIsResumingCheckpoint(false);
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          type: "text",
          content: "브라우저 작업을 다시 시작하지 못했습니다. 잠시 후 다시 눌러주세요.",
          timestamp: new Date(),
        },
      ]);
    }
  }

  async function handleOrderSelected(selectedOrder: SelectedOrder) {
    const orderTypeText = selectedOrder.orderType === "delivery" ? "배달" : "포장";
    const optionText =
      selectedOrder.options.length > 0 ? ` 옵션: ${selectedOrder.options.join(", ")}` : "";

    await handleSend(
      `${selectedOrder.menuName}${optionText} ${orderTypeText} 주문 준비해줘.`,
      selectedOrder
    );
  }

  if (sessionError) {
    return (
      <div className="mx-auto flex h-full w-full max-w-6xl items-center justify-center rounded-[2rem] border border-gray-200 bg-white shadow-[var(--shadow)]">
        <div className="flex flex-col items-center gap-4 px-8 text-center">
          <p className="text-sm font-medium text-gray-600">
            서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.
          </p>
          <button
            onClick={handleRetry}
            className="rounded-full bg-[var(--accent)] px-5 py-2 text-sm font-bold text-white shadow-[0_10px_24px_rgba(232,25,44,0.28)] hover:-translate-y-0.5 transition"
          >
            다시 연결
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-gray-200 bg-white shadow-[var(--shadow)]">
      <header className="shrink-0 border-b border-[var(--line)] bg-[#1a1a1a] px-5 py-4 sm:px-7">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-[var(--accent)]">
              <Image src="/bbq-mascot.png" alt="BBQ 마스코트" width={44} height={44} className="object-cover" />
            </div>
            <div>
              <h1 className="font-display text-2xl text-white leading-none">
                bb·q
                <span className="ml-2 text-[var(--accent)]">AI</span>
              </h1>
            </div>
          </div>

        </div>

      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[#f8f8f8] px-2 pb-2 sm:px-3 sm:pb-3">
        <MessageList
          messages={messages}
          isLoading={isLoading}
          onOrderSelected={handleOrderSelected}
          manualCheckpoint={manualCheckpoint}
          isResumingCheckpoint={isResumingCheckpoint}
          onResumeCheckpoint={handleResumeCheckpoint}
          streamingContent={streamingContent}
          currentIntent={currentIntent}
        />
        <InputBar onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}

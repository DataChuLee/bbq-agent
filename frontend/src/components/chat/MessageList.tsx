"use client";

import { useEffect, useRef } from "react";
import { ManualCheckpoint, Message, SelectedOrder } from "@/types/chat";
import { ManualCheckpointCard } from "./ManualCheckpointCard";
import { MessageBubble } from "./MessageBubble";
import { MenuCardList } from "./MenuCardList";
import { OrderStatusCard } from "./OrderStatusCard";
import { SourceList } from "./SourceList";
import { TypingIndicator } from "./TypingIndicator";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onOrderSelected: (selectedOrder: SelectedOrder) => void;
  manualCheckpoint: ManualCheckpoint | null;
  isResumingCheckpoint: boolean;
  onResumeCheckpoint: () => void;
  /** 스트리밍 중 누적 토큰. null이면 스트리밍 없음 */
  streamingContent: string | null;
  currentIntent: string | null;
}

export function MessageList({
  messages,
  isLoading,
  onOrderSelected,
  manualCheckpoint,
  isResumingCheckpoint,
  onResumeCheckpoint,
  streamingContent,
  currentIntent,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, manualCheckpoint, streamingContent]);

  const isStreaming = streamingContent !== null;

  return (
    <div className="flex-1 overflow-y-auto px-2 py-5 sm:px-4 sm:py-6">
      {messages.length === 0 && !isStreaming && (
        <div className="flex h-full flex-col items-center justify-center px-6 py-8 text-center">
          <div className="w-full max-w-3xl rounded-2xl border border-gray-200 bg-white px-6 py-8 shadow-[0_4px_24px_rgba(0,0,0,0.08)] sm:px-10 sm:py-10">
            <div className="mx-auto flex max-w-2xl flex-col items-center">
              <h2 className="font-display text-3xl text-gray-900 sm:text-4xl">
                오늘 먹고 싶은 BBQ를
                <span className="block text-[var(--accent)]">바로 골라드립니다.</span>
              </h2>
              <p className="mt-4 max-w-xl text-sm leading-7 text-gray-500 sm:text-base">
                취향에 맞는 메뉴 추천부터 주문 관련 안내, 고객 문의까지 자연스럽게
                이어서 물어보세요. 매운맛, 1인 메뉴, 사이드 조합처럼 구체적으로
                입력할수록 더 정확하게 답변합니다.
              </p>

              <div className="mt-8 grid w-full gap-3 sm:grid-cols-3">
                {[
                  ["🍗", "메뉴 추천", "매운 치킨, 마라풍, 바삭한 식감처럼 취향 기반 추천"],
                  ["📦", "주문 안내", "주문 변경, 취소, 배달 관련 문의를 빠르게 안내"],
                  ["🔍", "메뉴 탐색", "신메뉴, 인기 메뉴, 1인 메뉴를 한 번에 탐색"],
                ].map(([icon, title, desc]) => (
                  <div
                    key={title}
                    className="flex flex-col items-center rounded-xl border border-gray-100 bg-gray-50 px-4 py-5 text-center transition hover:border-[var(--accent)]/30 hover:bg-red-50/40 hover:shadow-sm"
                  >
                    <span className="mb-2 text-2xl">{icon}</span>
                    <p className="text-sm font-bold text-gray-900">{title}</p>
                    <p className="mt-1.5 text-xs leading-5 text-gray-500">{desc}</p>
                  </div>
                ))}
              </div>

              <div className="mt-8 flex flex-wrap justify-center gap-2.5">
                {["매운 치킨 추천해줘", "주문 취소는 어떻게 해?", "1인 메뉴 뭐 있어?"].map(
                  (suggestion) => (
                    <span
                      key={suggestion}
                      className="rounded-full border border-[var(--accent)]/30 bg-red-50 px-4 py-2 text-xs font-semibold text-[var(--accent)]"
                    >
                      {suggestion}
                    </span>
                  )
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
        {messages.map((message) => {
          if (message.type === "menu_cards") {
            return (
              <div key={message.id}>
                <MenuCardList
                  isLoading={isLoading}
                  message={message}
                  onOrderSelected={onOrderSelected}
                />
                {message.sources && message.sources.length > 0 ? (
                  <div className="ml-12">
                    <SourceList sources={message.sources} />
                  </div>
                ) : null}
              </div>
            );
          }
          if (message.type === "order_status") {
            return <OrderStatusCard key={message.id} message={message} />;
          }
          return <MessageBubble key={message.id} message={message} />;
        })}

        {manualCheckpoint ? (
          <ManualCheckpointCard
            checkpoint={manualCheckpoint}
            isResuming={isResumingCheckpoint}
            onResume={onResumeCheckpoint}
          />
        ) : null}

        {/* 스트리밍 중: 토큰이 쌓이면 말풍선으로, 아직 없으면 TypingIndicator */}
        {manualCheckpoint ? null : isStreaming && streamingContent ? (
          <MessageBubble
            message={{
              id: "streaming",
              role: "assistant",
              type: "text",
              content: streamingContent,
              timestamp: new Date(),
            }}
          />
        ) : isLoading ? (
          <TypingIndicator key={currentIntent ?? "pending"} intent={currentIntent} />
        ) : null}
      </div>

      <div ref={bottomRef} />
    </div>
  );
}

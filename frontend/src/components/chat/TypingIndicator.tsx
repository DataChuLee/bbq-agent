"use client";

import { useEffect, useState } from "react";

const STATUS_MAP: Record<string, string[]> = {
  menu: [
    "메뉴를 검색하고 있어요...",
    "취향에 맞는 메뉴를 고르고 있어요...",
    "추천을 준비하고 있어요...",
  ],
  menu_followup: [
    "추가 메뉴를 찾고 있어요...",
    "다른 선택지를 확인하고 있어요...",
    "추천을 업데이트하고 있어요...",
  ],
  cs: [
    "문의 내용을 파악하고 있어요...",
    "관련 정보를 검색하고 있어요...",
    "답변을 생성하고 있어요...",
  ],
  unknown: [
    "요청을 분석하고 있어요...",
    "정보를 확인하고 있어요...",
    "답변을 생성하고 있어요...",
  ],
};

interface TypingIndicatorProps {
  intent?: string | null;
}

export function TypingIndicator({ intent }: TypingIndicatorProps) {
  const [visibleCount, setVisibleCount] = useState(0);

  const steps = STATUS_MAP[intent ?? ""] ?? null;

  useEffect(() => {
    if (!intent || !STATUS_MAP[intent]) return;

    const timers = [
      setTimeout(() => setVisibleCount(1), 0),
      setTimeout(() => setVisibleCount(2), 1500),
      setTimeout(() => setVisibleCount(3), 3000),
    ];
    return () => {
      timers.forEach(clearTimeout);
    };
  }, [intent]);

  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <div className="rounded-[1.4rem] rounded-tl-sm border border-gray-200 bg-white px-4 py-3 shadow-[0_4px_16px_rgba(0,0,0,0.06)]">
        {!steps ? (
          /* intent 수신 전: 점 3개 */
          <div className="flex h-4 items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        ) : (
          /* intent 수신 후: 순차 등장 목록 */
          <ul className="flex flex-col gap-1.5">
            {steps.map((label, i) => (
              <li
                key={label}
                className={`flex items-center gap-2 text-xs transition-all duration-500 ${
                  i < visibleCount ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1 pointer-events-none"
                } ${i === visibleCount - 1 ? "text-[var(--accent)] font-semibold" : "text-gray-400"}`}
              >
                {i === visibleCount - 1 ? (
                  <span className="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
                ) : (
                  <span className="inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2 border-gray-300 bg-gray-100" />
                )}
                {label}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

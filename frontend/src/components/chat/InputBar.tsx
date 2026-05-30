"use client";

import { KeyboardEvent, useRef, useState } from "react";

interface InputBarProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function InputBar({ onSend, isLoading }: InputBarProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  const canSend = value.trim().length > 0 && !isLoading;

  return (
    <div className="shrink-0 px-2 pb-2 sm:px-4 sm:pb-4">
      <div className="mx-auto max-w-4xl rounded-2xl border border-gray-200 bg-white p-3 shadow-[0_4px_20px_rgba(0,0,0,0.08)]">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleInput}
              rows={1}
              placeholder="원하는 메뉴나 문의 내용을 입력하세요. 예: 바삭하고 매운 치킨 추천해줘"
              disabled={isLoading}
              aria-label="메시지 입력"
              className="w-full resize-none overflow-hidden rounded-xl border border-gray-200 bg-gray-50 px-4 py-3.5 text-sm leading-7 text-gray-800 placeholder:text-gray-400 focus:border-[var(--accent)] focus:bg-white focus:outline-none disabled:opacity-60"
              style={{ minHeight: "48px", maxHeight: "160px" }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!canSend}
            aria-label="전송"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-white shadow-[0_4px_16px_rgba(232,25,44,0.30)] transition hover:bg-[var(--accent-deep)] hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-5 w-5 -rotate-45"
              aria-hidden="true"
            >
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

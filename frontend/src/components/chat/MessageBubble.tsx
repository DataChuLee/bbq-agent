import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ClarificationMessage, TextMessage } from "@/types/chat";
import { SourceList } from "./SourceList";

interface MessageBubbleProps {
  message: TextMessage | ClarificationMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isClarification = message.type === "clarification";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] rounded-[1.4rem] rounded-tr-sm bg-[var(--accent)] px-4 py-3 text-white shadow-[0_8px_24px_rgba(232,25,44,0.24)] sm:px-5">
          <p className="text-sm leading-7">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <div className="max-w-[82%] min-w-0">
        {isClarification && (
          <div className="mb-2 flex items-center gap-2">
            <span
              className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-[11px] font-bold text-[var(--accent)]"
              aria-hidden="true"
            >
              ?
            </span>
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
              추가 정보가 필요합니다
            </span>
          </div>
        )}
        <div
          className={`rounded-[1.4rem] rounded-tl-sm border px-4 py-3 shadow-[0_4px_16px_rgba(0,0,0,0.06)] sm:px-5 ${
            isClarification
              ? "border-red-100 bg-red-50 text-gray-800"
              : "border-gray-200 bg-white text-gray-700"
          }`}
          style={!isClarification ? { borderLeftColor: "var(--accent)", borderLeftWidth: "3px" } : undefined}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => (
                <p className="mb-2 text-sm leading-7 last:mb-0">
                  {children}
                </p>
              ),
              strong: ({ children }) => (
                <strong className="font-bold text-gray-900">{children}</strong>
              ),
              ol: ({ children }) => (
                <ol className="mb-2 list-decimal space-y-1 pl-5 text-sm leading-7 last:mb-0">
                  {children}
                </ol>
              ),
              ul: ({ children }) => (
                <ul className="mb-2 list-disc space-y-1 pl-5 text-sm leading-7 last:mb-0">
                  {children}
                </ul>
              ),
              li: ({ children }) => <li className="leading-7">{children}</li>,
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.type === "text" &&
          message.role === "assistant" &&
          message.sources &&
          message.sources.length > 0 && (
            <SourceList sources={message.sources} />
          )}
      </div>
    </div>
  );
}

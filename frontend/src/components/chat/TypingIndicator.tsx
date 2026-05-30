export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <div className="rounded-[1.4rem] rounded-tl-sm border border-gray-200 bg-white px-4 py-3 shadow-[0_4px_16px_rgba(0,0,0,0.06)]">
        <div className="flex h-4 items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="h-2.5 w-2.5 rounded-full bg-[var(--accent)] animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
      </div>
    </div>
  );
}

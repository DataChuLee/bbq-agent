"use client";

import { useState } from "react";
import { Source } from "@/types/chat";

interface SourceListProps {
  sources: Source[];
}

export function SourceList({ sources }: SourceListProps) {
  const [open, setOpen] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="mt-2.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-gray-400 transition-colors hover:text-gray-600"
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <span>참고 자료 {sources.length}건</span>
        <span className="text-[10px]">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((source, i) => {
            const rawCategory =
              source.metadata.cs_category ??
              source.metadata.name ??
              source.metadata.category;
            const category = rawCategory == null ? "" : String(rawCategory);

            return (
              <li
                key={`${source.sourceType}:${source.content}:${i}`}
                className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5"
              >
                <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                  <span className="inline-block rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
                    {source.sourceType === "menu" ? "메뉴" : "고객지원"}
                  </span>
                  {category && (
                    <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-500">
                      {category}
                    </span>
                  )}
                </div>
                <p className="line-clamp-2 text-xs leading-5 text-gray-500">
                  {source.content}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

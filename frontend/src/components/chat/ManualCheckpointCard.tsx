"use client";

import { ManualCheckpoint } from "@/types/chat";

interface ManualCheckpointCardProps {
  checkpoint: ManualCheckpoint;
  isResuming: boolean;
  onResume: () => void;
}

export function ManualCheckpointCard({
  checkpoint,
  isResuming,
  onResume,
}: ManualCheckpointCardProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <article className="w-full max-w-[82%] rounded-[1.4rem] rounded-tl-sm border border-amber-200 bg-white px-4 py-4 shadow-[0_4px_16px_rgba(0,0,0,0.06)] sm:px-5">
        <div className="mb-3 inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-black text-amber-900">
          직접 확인 필요
        </div>
        <h3 className="text-base font-black leading-6 text-gray-950">
          브라우저에서 로그인을 완료해주세요
        </h3>
        <p className="mt-2 text-sm leading-6 text-gray-600">
          {checkpoint.message ||
            "열린 BBQ 브라우저에서 로그인과 주소 선택을 마친 뒤 아래 버튼을 눌러주세요."}
        </p>
        <button
          type="button"
          onClick={onResume}
          disabled={isResuming}
          className="mt-4 inline-flex min-h-11 items-center justify-center rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-black text-white shadow-[0_8px_20px_rgba(232,25,44,0.22)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
        >
          {isResuming ? "계속 준비 중..." : "완료했어요"}
        </button>
      </article>
    </div>
  );
}

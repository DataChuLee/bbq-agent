"use client";

import { OrderStatusMessage } from "@/types/chat";

interface OrderStatusCardProps {
  message: OrderStatusMessage;
}

function formatOrderType(orderType: string): string {
  if (orderType === "pickup") return "포장";
  if (orderType === "delivery") return "배달";
  return "미정";
}

function getStatusLabel(status: string): string {
  if (status === "option_review") return "옵션 확인 필요";
  if (status === "failed") return "주문 준비 실패";
  return "장바구니 확인";
}

function getStatusClasses(status: string): string {
  if (status === "option_review") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }

  if (status === "failed") {
    return "border-red-200 bg-red-50 text-red-900";
  }

  return "border-emerald-200 bg-emerald-50 text-emerald-900";
}

export function OrderStatusCard({ message }: OrderStatusCardProps) {
  const { order } = message;
  const statusClasses = getStatusClasses(order.status);

  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <article className="w-full max-w-[82%] rounded-[1.4rem] rounded-tl-sm border border-gray-200 bg-white px-4 py-4 shadow-[0_4px_16px_rgba(0,0,0,0.06)] sm:px-5">
        <div
          className={`mb-4 inline-flex rounded-full border px-3 py-1 text-[11px] font-black ${statusClasses}`}
        >
          {getStatusLabel(order.status)}
        </div>

        <h3 className="text-base font-black leading-6 text-gray-950">
          {order.menuName || "선택한 메뉴"}
        </h3>
        <p className="mt-2 text-sm leading-6 text-gray-600">{order.message}</p>

        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-2.5">
            <dt className="text-[10px] font-black uppercase tracking-[0.16em] text-gray-400">
              주문 방식
            </dt>
            <dd className="mt-1 font-bold text-gray-800">
              {formatOrderType(order.orderType)}
            </dd>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-2.5">
            <dt className="text-[10px] font-black uppercase tracking-[0.16em] text-gray-400">
              옵션
            </dt>
            <dd className="mt-1 font-bold leading-5 text-gray-800">
              {(order.selectedOptions?.length ?? 0) > 0
                ? order.selectedOptions?.join(", ")
                : order.expectedOptions.length > 0
                  ? order.expectedOptions.join(", ")
                  : "추가 옵션 없음"}
            </dd>
          </div>
          {(order.missingOptions?.length ?? 0) > 0 ? (
            <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2.5 sm:col-span-2">
              <dt className="text-[10px] font-black uppercase tracking-[0.16em] text-amber-600">
                확인 필요 옵션
              </dt>
              <dd className="mt-1 font-bold leading-5 text-amber-900">
                {order.missingOptions?.join(", ")}
              </dd>
            </div>
          ) : null}
        </dl>

        <div className="mt-4 rounded-xl border border-red-100 bg-red-50/70 px-3.5 py-3">
          <p className="text-sm font-semibold leading-6 text-gray-800">
            {order.nextAction || "BBQ 공식 사이트에서 장바구니와 결제를 확인해 주세요."}
          </p>
          {order.currentUrl ? (
            <a
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-black text-[var(--accent)]"
              href={order.currentUrl}
              target="_blank"
              rel="noreferrer"
            >
              현재 BBQ 페이지
            </a>
          ) : null}
        </div>
      </article>
    </div>
  );
}

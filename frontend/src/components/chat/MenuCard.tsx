"use client";

import Image from "next/image";
import { useState } from "react";
import {
  MenuCard as MenuCardType,
  OrderType,
  SelectedOrder,
} from "@/types/chat";
import {
  getSelectionDetails,
  OptionSelectorModal,
  parseMenuOptionGroups,
  SelectedOptions,
} from "./OptionSelectorModal";

interface MenuCardProps {
  card: MenuCardType;
  isLoading: boolean;
  onOrderSelected: (selectedOrder: SelectedOrder) => void;
}

type DetailItem = {
  label: string;
  value: string;
};

const DETAIL_LABELS: Record<string, string> = {
  알레르기: "알레르기",
  맵기: "맵기",
  식감: "식감",
  옵션: "옵션",
  구성: "구성",
  영양: "영양",
  영양정보: "영양",
  칼로리: "칼로리",
};

function normalizeText(value?: string): string {
  return value?.replace(/\s+/g, " ").trim() ?? "";
}

function formatReadable(value: string): string {
  return normalizeText(value).replace(/\s*\/\s*/g, " · ");
}

function getOptionSummary(value: string): string {
  const optionGroups = parseMenuOptionGroups(value);
  if (optionGroups.length === 0) {
    return value.trim().startsWith("[") ? "선택 옵션 있음" : formatReadable(value);
  }

  return `옵션 그룹 ${optionGroups.length}개`;
}

function getDescriptionSegments(description: string): string[] {
  return normalizeText(description)
    .split("|")
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function getOptionValueFromDescription(description: string): string {
  for (const segment of getDescriptionSegments(description)) {
    const optionSegment = segment.match(/^옵션\s*[:：]?\s*(.+)$/);
    if (optionSegment) {
      return optionSegment[1].trim();
    }
  }

  return "";
}

function getCardOptionValue(card: MenuCardType): string {
  return card.options || getOptionValueFromDescription(card.description);
}

function getFactEntries(value: string): Array<{ label: string; value: string }> {
  return value
    .split(/,\s*(?=[^,]+:\s*)/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const matched = entry.match(/^([^:：]+)\s*[:：]\s*(.+)$/);
      if (!matched) {
        return { label: "", value: entry };
      }

      return {
        label: normalizeText(matched[1]),
        value: normalizeText(matched[2]),
      };
    });
}

function getCardDetails(card: MenuCardType): {
  summary: string;
  notes: string[];
  facts: DetailItem[];
  allergy: string;
} {
  const factsMap = new Map<string, string>();
  const descriptionSegments = getDescriptionSegments(card.description);
  const contentSegments: string[] = [];
  let allergy = formatReadable(card.allergy ?? "");

  for (const segment of descriptionSegments) {
    if (segment === card.name || segment === card.category) {
      continue;
    }

    const optionSegment = segment.match(/^옵션\s*[:：]?\s*(.+)$/);
    if (optionSegment) {
      factsMap.set("옵션", getOptionSummary(optionSegment[1]));
      continue;
    }

    const matchedDetail = segment.match(/^([^:：]+)\s*[:：]\s*(.+)$/);
    if (matchedDetail) {
      const rawLabel = normalizeText(matchedDetail[1]);
      const label = DETAIL_LABELS[rawLabel] ?? rawLabel;
      const value =
        label === "옵션"
          ? getOptionSummary(matchedDetail[2])
          : formatReadable(matchedDetail[2]);

      if (label === "알레르기") {
        if (!allergy) {
          allergy = value;
        }
        continue;
      }

      if (!factsMap.has(label)) {
        factsMap.set(label, value);
      }
      continue;
    }

    contentSegments.push(formatReadable(segment));
  }

  const optionValue = getCardOptionValue(card);
  if (optionValue && !factsMap.has("옵션")) {
    factsMap.set("옵션", getOptionSummary(optionValue));
  }

  if (card.nutrition && !factsMap.has("영양")) {
    factsMap.set("영양", formatReadable(card.nutrition));
  }

  const [summary = "", ...notes] = contentSegments;
  const facts: DetailItem[] = [
    { label: "카테고리", value: formatReadable(card.category) },
    ...Array.from(factsMap.entries(), ([label, value]) => ({ label, value })),
  ].filter((item) => item.value);

  return { summary, notes, facts, allergy };
}

export function MenuCard({ card, isLoading, onOrderSelected }: MenuCardProps) {
  const [imageHidden, setImageHidden] = useState(false);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [orderType, setOrderType] = useState<OrderType>("delivery");
  const [selectedOptions, setSelectedOptions] = useState<SelectedOptions>({
    required: {},
    optional: {},
  });
  const hasImage = Boolean(card.imageURL);
  const showImage = hasImage && !imageHidden;
  const optionGroups = parseMenuOptionGroups(getCardOptionValue(card));
  const selectionDetails = getSelectionDetails(optionGroups, selectedOptions);
  const totalPrice = card.price + selectionDetails.addPrice;
  const formattedPrice = new Intl.NumberFormat("ko-KR").format(totalPrice);
  const { summary, notes, facts, allergy } = getCardDetails(card);
  const hasExpandableDetails =
    summary.length > 70 || notes.some((note) => note.length > 45);

  function handleOrderSelected() {
    onOrderSelected({
      menuName: card.name,
      menuCategory: card.category,
      options: selectionDetails.names,
      optionDetails: selectionDetails.details,
      orderType,
    });
  }

  return (
    <>
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-[0_4px_20px_rgba(0,0,0,0.08)] transition duration-200 hover:-translate-y-1 hover:shadow-[0_12px_32px_rgba(0,0,0,0.14)]">
      {hasImage ? (
        <div className="relative aspect-[4/3] overflow-hidden border-b border-gray-200 bg-gray-100">
          {showImage ? (
            <Image
              src={card.imageURL!}
              alt={card.name}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
              className="object-cover transition duration-300 group-hover:scale-[1.03]"
              onError={() => setImageHidden(true)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(circle_at_top,_#f8d7da,_#f3f4f6_55%)] px-4 text-center text-[11px] font-bold uppercase tracking-[0.24em] text-gray-500">
              BBQ Menu
            </div>
          )}
        </div>
      ) : null}

      <div className="bg-[#1a1a1a] px-4 py-3 text-white">
        <div className="grid h-[72px] grid-cols-[minmax(0,1fr)_4.5rem] items-center gap-3">
          <h3
            className="overflow-hidden text-[15px] font-bold leading-[1.35]"
            style={{
              display: "-webkit-box",
              WebkitBoxOrient: "vertical",
              WebkitLineClamp: 2,
            }}
          >
            {card.name}
          </h3>
          <span className="flex h-10 w-[4.5rem] shrink-0 items-center justify-center rounded-md bg-[var(--accent)] px-2 text-white">
            <span
              className="text-center text-[11px] font-bold leading-tight"
              style={{ wordBreak: "keep-all" }}
            >
              {card.category}
            </span>
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 p-4">
        {card.recommendationReason ? (
          <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-3">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[var(--accent)]">
              추천 이유
            </p>
            <p className="mt-2 text-[13px] font-semibold leading-5 text-gray-700">
              {card.recommendationReason}
            </p>
          </div>
        ) : null}

        {summary ? (
          <div className="rounded-2xl border border-red-100 bg-[linear-gradient(180deg,rgba(255,248,248,1)_0%,rgba(255,255,255,1)_100%)] px-4 py-3.5">
            <p
              className={[
                "text-sm leading-6 text-gray-700",
                detailsExpanded ? "" : "overflow-hidden",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{
                display: "-webkit-box",
                WebkitBoxOrient: "vertical",
                WebkitLineClamp: detailsExpanded ? "unset" : 3,
              }}
            >
              {summary}
            </p>
            {notes.length > 0 ? (
              <div className="mt-3 space-y-2 border-t border-red-100 pt-3">
                {notes.map((note, index) => (
                  <p
                    key={`${card.name}-note-${index}`}
                    className={[
                      "text-[13px] leading-5 text-gray-500",
                      detailsExpanded ? "" : "overflow-hidden",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{
                      display: "-webkit-box",
                      WebkitBoxOrient: "vertical",
                      WebkitLineClamp: detailsExpanded ? "unset" : 2,
                    }}
                  >
                    {note}
                  </p>
                ))}
              </div>
            ) : null}
            {hasExpandableDetails ? (
              <button
                type="button"
                className="mt-3 text-[12px] font-bold text-[var(--accent)]"
                onClick={() => setDetailsExpanded((current) => !current)}
                aria-expanded={detailsExpanded}
              >
                {detailsExpanded ? "접기" : "더보기"}
              </button>
            ) : null}
          </div>
        ) : null}

        {facts.length > 0 ? (
          <div className="grid grid-cols-2 items-start gap-2">
            {facts.map((fact) => {
              const isNutrition = fact.label === "영양";
              const isOptions = fact.label === "옵션" && optionGroups.length > 0;
              const factEntries = isNutrition ? getFactEntries(fact.value) : [];

              return (
                <div
                  key={`${card.name}-${fact.label}`}
                  className={[
                    "rounded-xl border border-gray-100 bg-gray-50/90 px-3 py-2.5",
                    isNutrition ? "col-span-2 px-3.5 py-3" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-gray-400">
                    {fact.label}
                  </p>
                  {isOptions ? (
                    <div className="mt-2">
                      <button
                        type="button"
                        className="w-full rounded-lg bg-[var(--accent)] px-3 py-2 text-left text-[12px] font-black text-white"
                        onClick={() => setOptionsOpen(true)}
                      >
                        옵션 선택
                      </button>
                      {selectionDetails.count > 0 ? (
                        <p className="mt-2 text-[12px] font-semibold leading-5 text-gray-600">
                          선택 {selectionDetails.count}개 · +
                          {new Intl.NumberFormat("ko-KR").format(selectionDetails.addPrice)}원
                        </p>
                      ) : null}
                    </div>
                  ) : isNutrition && factEntries.length > 0 ? (
                    <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2">
                      {factEntries.map((entry, index) => (
                        <div key={`${card.name}-${fact.label}-${index}`} className="min-w-0">
                          {entry.label ? (
                            <p className="text-[11px] font-semibold leading-4 text-gray-500">
                              {entry.label}
                            </p>
                          ) : null}
                          <p className="mt-0.5 text-[13px] font-bold leading-5 text-gray-700">
                            {entry.value}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-1 text-[13px] font-semibold leading-5 text-gray-700">
                      {fact.value}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ) : null}

        <div className="mt-auto space-y-4 pt-2">
          {allergy ? (
            <div className="flex h-[96px] flex-col justify-center rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-700">
                알레르기
              </p>
              <p
                className="mt-2 overflow-hidden text-[13px] leading-6 text-amber-900"
                style={{
                  display: "-webkit-box",
                  WebkitBoxOrient: "vertical",
                  WebkitLineClamp: 2,
                }}
              >
                {allergy}
              </p>
            </div>
          ) : null}
          <div className="flex items-end justify-between border-t border-gray-100 pt-4">
            <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">
              가격
            </p>
            <span className="text-xl font-black tracking-tight text-[var(--accent)]">
              {formattedPrice}원
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              ["delivery", "배달"],
              ["pickup", "포장"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={[
                  "h-10 rounded-lg border text-[12px] font-black transition",
                  orderType === value
                    ? "border-[var(--accent)] bg-red-50 text-[var(--accent)]"
                    : "border-gray-200 bg-white text-gray-600",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => setOrderType(value as OrderType)}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="h-11 w-full rounded-xl bg-[#1a1a1a] text-sm font-black text-white transition hover:bg-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isLoading}
            onClick={handleOrderSelected}
          >
            주문 준비
          </button>
        </div>
      </div>
    </article>
    {optionsOpen ? (
      <OptionSelectorModal
        basePrice={card.price}
        groups={optionGroups}
        menuName={card.name}
        onClose={() => setOptionsOpen(false)}
        onSelectionChange={setSelectedOptions}
        selection={selectedOptions}
      />
    ) : null}
    </>
  );
}

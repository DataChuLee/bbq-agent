"use client";

import type { SelectedOptionDetail } from "@/types/chat";

type RawRecord = Record<string, unknown>;

export type MenuOption = {
  id: string;
  name: string;
  addPrice: number;
};

export type MenuOptionGroup = {
  id: string;
  maxSelectCount: number;
  name: string;
  requiredOptions: MenuOption[];
  optionalOptions: MenuOption[];
};

export type SelectedOptions = {
  required: Record<string, string>;
  optional: Record<string, string[]>;
};

interface OptionSelectorModalProps {
  basePrice: number;
  groups: MenuOptionGroup[];
  menuName: string;
  onClose: () => void;
  onSelectionChange: (selection: SelectedOptions) => void;
  selection: SelectedOptions;
}

function isRecord(value: unknown): value is RawRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeText(value: unknown): string {
  return typeof value === "string" ? value.replace(/\s+/g, " ").trim() : "";
}

function normalizePrice(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value.replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function parseOptionList(value: unknown, groupIndex: number): MenuOption[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item, optionIndex) => {
      if (!isRecord(item)) {
        return null;
      }

      const name = normalizeText(item.name);
      if (!name) {
        return null;
      }

      return {
        id: `${groupIndex}-${optionIndex}-${name}`,
        name,
        addPrice: normalizePrice(item.add_price),
      };
    })
    .filter((item): item is MenuOption => item !== null);
}

function getSelectCount(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function parseJsonValue(value: string): unknown | null {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function parseOptionRoot(value: string): unknown {
  let parsed: unknown = value.trim();

  for (let index = 0; index < 2; index += 1) {
    if (typeof parsed !== "string") {
      break;
    }

    const text = parsed.trim();
    if (!text.startsWith("[") && !text.startsWith("{")) {
      break;
    }

    const next = parseJsonValue(text);
    if (next === null) {
      break;
    }

    parsed = next;
  }

  return parsed;
}

function collectOptionGroups(value: unknown): RawRecord[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectOptionGroups(item));
  }

  if (!isRecord(value)) {
    return [];
  }

  if (
    Array.isArray(value.required_select) ||
    Array.isArray(value.optional_select) ||
    Array.isArray(value.items) ||
    typeof value.group_name === "string"
  ) {
    return [value];
  }

  return [];
}

export function parseMenuOptionGroups(value?: string): MenuOptionGroup[] {
  if (!value) {
    return [];
  }

  const parsed = parseOptionRoot(value);
  const rawGroups = collectOptionGroups(parsed);
  if (rawGroups.length === 0) {
    return [];
  }

  return rawGroups
    .map((item, groupIndex) => {
      const itemOptions = parseOptionList(item.items, groupIndex);
      const requiredSelectCount = getSelectCount(item.required_select_count);
      const requiredOptions = [
        ...parseOptionList(item.required_select, groupIndex),
        ...(requiredSelectCount > 0 ? itemOptions : []),
      ];
      const optionalOptions = [
        ...parseOptionList(item.optional_select, groupIndex),
        ...(requiredSelectCount === 0 ? itemOptions : []),
      ];

      if (requiredOptions.length === 0 && optionalOptions.length === 0) {
        return null;
      }

      return {
        id: `${groupIndex}-${normalizeText(item.group_name) || "option"}`,
        maxSelectCount: getSelectCount(item.max_select_count),
        name: normalizeText(item.group_name) || `옵션 ${groupIndex + 1}`,
        requiredOptions,
        optionalOptions,
      };
    })
    .filter((item): item is MenuOptionGroup => item !== null);
}

export function getSelectionDetails(
  groups: MenuOptionGroup[],
  selection: SelectedOptions
): {
  count: number;
  addPrice: number;
  names: string[];
  details: SelectedOptionDetail[];
} {
  let count = 0;
  let addPrice = 0;
  const names: string[] = [];
  const details: SelectedOptionDetail[] = [];

  for (const group of groups) {
    const selectedRequired =
      group.requiredOptions.find(
        (option) => option.id === selection.required[group.id]
      ) ?? group.requiredOptions[0];

    if (selectedRequired) {
      count += 1;
      addPrice += selectedRequired.addPrice;
      names.push(selectedRequired.name);
      details.push({
        groupName: group.name,
        optionName: selectedRequired.name,
        addPrice: selectedRequired.addPrice,
        required: true,
      });
    }

    const selectedOptionalIds = new Set(selection.optional[group.id] ?? []);
    for (const option of group.optionalOptions) {
      if (!selectedOptionalIds.has(option.id)) {
        continue;
      }

      count += 1;
      addPrice += option.addPrice;
      names.push(option.name);
      details.push({
        groupName: group.name,
        optionName: option.name,
        addPrice: option.addPrice,
        required: false,
      });
    }
  }

  return { count, addPrice, names, details };
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

export function OptionSelectorModal({
  basePrice,
  groups,
  menuName,
  onClose,
  onSelectionChange,
  selection,
}: OptionSelectorModalProps) {
  const { addPrice, count } = getSelectionDetails(groups, selection);
  const totalPrice = basePrice + addPrice;

  const selectRequired = (groupId: string, optionId: string) => {
    onSelectionChange({
      ...selection,
      required: {
        ...selection.required,
        [groupId]: optionId,
      },
    });
  };

  const toggleOptional = (group: MenuOptionGroup, optionId: string) => {
    const groupId = group.id;
    const current = new Set(selection.optional[groupId] ?? []);
    if (current.has(optionId)) {
      current.delete(optionId);
    } else {
      if (group.maxSelectCount > 0 && current.size >= group.maxSelectCount) {
        return;
      }

      current.add(optionId);
    }

    onSelectionChange({
      ...selection,
      optional: {
        ...selection.optional,
        [groupId]: Array.from(current),
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 px-3 py-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="option-selector-title"
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-[0_24px_80px_rgba(0,0,0,0.28)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-gray-100 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-[var(--accent)]">
                옵션 선택
              </p>
              <h2 id="option-selector-title" className="mt-1 text-lg font-black text-gray-950">
                {menuName}
              </h2>
            </div>
            <button
              type="button"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gray-200 text-lg font-bold text-gray-500"
              onClick={onClose}
              aria-label="옵션 선택 닫기"
            >
              ×
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {groups.map((group) => (
            <section key={group.id} className="space-y-3">
              <div>
                <h3 className="text-sm font-black text-gray-900">{group.name}</h3>
                <p className="mt-0.5 text-[11px] font-semibold text-gray-400">
                  {group.requiredOptions.length > 0
                    ? "필수 선택"
                    : group.maxSelectCount > 0
                      ? `최대 ${group.maxSelectCount}개 선택`
                      : "추가 선택"}
                </p>
              </div>

              {group.requiredOptions.length > 0 ? (
                <div className="space-y-2">
                  {group.requiredOptions.map((option) => (
                    <label
                      key={option.id}
                      className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-gray-100 bg-gray-50 px-3.5 py-3"
                    >
                      <span className="flex min-w-0 items-center gap-3">
                        <input
                          type="radio"
                          name={group.id}
                          className="h-4 w-4 accent-[var(--accent)]"
                          checked={
                            (selection.required[group.id] ??
                              group.requiredOptions[0]?.id) === option.id
                          }
                          onChange={() => selectRequired(group.id, option.id)}
                        />
                        <span className="text-sm font-semibold text-gray-800">{option.name}</span>
                      </span>
                      <span className="shrink-0 text-sm font-black text-gray-900">
                        {option.addPrice > 0 ? `+${formatPrice(option.addPrice)}원` : "무료"}
                      </span>
                    </label>
                  ))}
                </div>
              ) : null}

              {group.optionalOptions.length > 0 ? (
                <div className="space-y-2">
                  {group.optionalOptions.map((option) => {
                    const checked = (selection.optional[group.id] ?? []).includes(option.id);

                    return (
                      <label
                        key={option.id}
                        className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-gray-100 bg-white px-3.5 py-3"
                      >
                        <span className="flex min-w-0 items-center gap-3">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-[var(--accent)]"
                            checked={checked}
                            onChange={() => toggleOptional(group, option.id)}
                          />
                          <span className="text-sm font-semibold text-gray-800">{option.name}</span>
                        </span>
                        <span className="shrink-0 text-sm font-black text-gray-900">
                          {option.addPrice > 0 ? `+${formatPrice(option.addPrice)}원` : "무료"}
                        </span>
                      </label>
                    );
                  })}
                </div>
              ) : null}
            </section>
          ))}
        </div>

        <div className="border-t border-gray-100 bg-white px-5 py-4">
          <div className="mb-3 flex items-end justify-between">
            <div>
              <p className="text-[11px] font-semibold text-gray-400">선택 {count}개</p>
              <p className="text-sm font-bold text-gray-700">
                기본 {formatPrice(basePrice)}원
                {addPrice > 0 ? ` + 옵션 ${formatPrice(addPrice)}원` : ""}
              </p>
            </div>
            <p className="text-2xl font-black text-[var(--accent)]">
              {formatPrice(totalPrice)}원
            </p>
          </div>
          <button
            type="button"
            className="h-12 w-full rounded-xl bg-[var(--accent)] text-sm font-black text-white"
            onClick={onClose}
          >
            선택 완료
          </button>
        </div>
      </div>
    </div>
  );
}

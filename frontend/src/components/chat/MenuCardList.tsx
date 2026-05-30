import { MenuCardsMessage, SelectedOrder } from "@/types/chat";
import { MenuCard } from "./MenuCard";

interface MenuCardListProps {
  isLoading: boolean;
  message: MenuCardsMessage;
  onOrderSelected: (selectedOrder: SelectedOrder) => void;
}

export function MenuCardList({
  isLoading,
  message,
  onOrderSelected,
}: MenuCardListProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-black text-white shadow-[0_4px_12px_rgba(232,25,44,0.24)]">
        B
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-3 flex items-center gap-2">
          <span
            className="inline-flex rounded-md bg-[var(--accent)] px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.2em] text-white"
            aria-hidden="true"
          >
            BBQ 추천
          </span>
          <p className="text-sm font-semibold text-gray-700">
            추천 메뉴 {message.cards.length}가지를 골라봤어요.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {message.cards.map((card, index) => (
            <MenuCard
              key={`${card.name}-${index}`}
              card={card}
              isLoading={isLoading}
              onOrderSelected={onOrderSelected}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

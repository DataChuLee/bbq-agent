export type MessageRole = "user" | "assistant";

export type Source = {
  sourceType: "menu" | "cs";
  content: string;
  score: number | null;
  metadata: Record<string, unknown>;
};

export type TextMessage = {
  id: string;
  role: MessageRole;
  type: "text";
  content: string;
  timestamp: Date;
  sources?: Source[];
};

export type MenuCard = {
  name: string;
  price: number;
  description: string;
  category: string;
  allergy?: string;
  nutrition?: string;
  options?: string;
  imageURL?: string;
  recommendationReason?: string;
  recommendationScore?: number;
  matchedCriteria?: string;
};

export type OrderType = "delivery" | "pickup";

export type SelectedOptionDetail = {
  groupName: string;
  optionName: string;
  addPrice: number;
  required: boolean;
};

export type SelectedOrder = {
  menuName: string;
  menuCategory: string;
  options: string[];
  optionDetails?: SelectedOptionDetail[];
  orderType: OrderType;
};

export type MenuCardsMessage = {
  id: string;
  role: "assistant";
  type: "menu_cards";
  cards: MenuCard[];
  timestamp: Date;
  sources?: Source[];
};

export type ClarificationMessage = {
  id: string;
  role: "assistant";
  type: "clarification";
  content: string;
  timestamp: Date;
};

export type OrderStatus = {
  status: "cart_ready" | "option_review" | "failed" | string;
  message: string;
  menuName: string;
  expectedOptions: string[];
  selectedOptions?: string[];
  missingOptions?: string[];
  orderType: OrderType | "";
  currentUrl: string;
  nextAction: string;
};

export type OrderStatusMessage = {
  id: string;
  role: "assistant";
  type: "order_status";
  order: OrderStatus;
  timestamp: Date;
};

export type ManualCheckpoint = {
  runId: string;
  message: string;
  createdAt?: Date;
};

export type Message =
  | TextMessage
  | MenuCardsMessage
  | ClarificationMessage
  | OrderStatusMessage;

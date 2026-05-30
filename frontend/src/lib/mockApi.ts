import { Message, MenuCard } from "@/types/chat";

const SAMPLE_MENU_CARDS: MenuCard[] = [
  {
    name: "황금올리브치킨",
    price: 20000,
    description: "바삭한 올리브유 튀김옷에 황금빛 색상의 시그니처 치킨. 담백하고 고소한 맛.",
    category: "후라이드",
    imageURL:
      "https://static.bbqorder.co.kr/menu/1ad843c458edeeefd04139c17_28f592e7-58f3-4083-b951-ebd9e630653f.png",
  },
  {
    name: "뿌링클",
    price: 21000,
    description: "달콤하고 짭짤한 치즈 파우더가 듬뿍! 남녀노소 누구나 좋아하는 스테디셀러.",
    category: "양념",
  },
  {
    name: "레드킹 치킨",
    price: 22000,
    description: "매콤달콤 양념과 바삭한 식감의 조화. 맥주 안주로 제격인 매운 치킨.",
    category: "매운맛",
    imageURL:
      "https://static.bbqorder.co.kr/menu/5688e109a6c1016fd6e2a921a_906bc0d4-ed43-4409-a976-5afb98e6d80d.png",
  },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export async function mockSendMessage(query: string): Promise<Message> {
  await delay(500);

  const lower = query.toLowerCase();

  const isMenuQuery =
    lower.includes("메뉴") ||
    lower.includes("치킨") ||
    lower.includes("추천") ||
    lower.includes("뭐") ||
    lower.includes("먹");

  const isCsQuery =
    lower.includes("배달") ||
    lower.includes("환불") ||
    lower.includes("주문") ||
    lower.includes("취소") ||
    lower.includes("결제") ||
    lower.includes("고객");

  if (isMenuQuery) {
    return {
      id: generateId(),
      role: "assistant",
      type: "menu_cards",
      cards: SAMPLE_MENU_CARDS,
      timestamp: new Date(),
    };
  }

  if (isCsQuery) {
    return {
      id: generateId(),
      role: "assistant",
      type: "text",
      content:
        "안녕하세요! BBQ 고객센터입니다. 문의하신 내용을 확인하겠습니다. 주문 번호나 추가 정보가 있으시면 알려주세요. 빠른 시간 내에 도움을 드리겠습니다.",
      timestamp: new Date(),
    };
  }

  return {
    id: generateId(),
    role: "assistant",
    type: "clarification",
    content:
      "좀 더 자세히 알려주시겠어요? 메뉴 추천을 원하시나요, 아니면 주문/배달 관련 문의이신가요?",
    timestamp: new Date(),
  };
}

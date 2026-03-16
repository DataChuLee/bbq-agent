from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    messages: List[BaseMessage]   # 전체 대화 이력 (Human + AI + Tool)
    intent: Optional[str]         # "menu" | "cs" | "unknown" — Intent Classifier 결과
    response: dict                # 최종 응답 (카드 JSON 또는 텍스트)

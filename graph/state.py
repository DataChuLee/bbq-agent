from typing import Annotated, Literal, NotRequired, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SelectedOrder(TypedDict):
    menu_name: str
    menu_category: NotRequired[str]
    options: list[str]
    option_details: NotRequired[list[dict]]
    order_type: Literal["delivery", "pickup"]


class AgentState(TypedDict):
    session_id: NotRequired[str]
    messages: Annotated[list[BaseMessage], add_messages]
    intent: Optional[str]
    response: dict
    menu_results: Optional[dict]
    cs_results: Optional[dict]
    selected_order: Optional[SelectedOrder]
    last_menu_query: Optional[str]
    last_cs_query: Optional[str]
    shown_menu_names: list[str]

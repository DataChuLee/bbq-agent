import asyncio
import queue
from collections.abc import AsyncIterator
from typing import Literal, Union

from api.services.manual_checkpoint import manual_checkpoint_broker
from api.services.session import SessionRecord

# 스트림 이벤트 타입: ("token", 토큰문자열) 또는 ("done", 응답dict, 의도문자열)
StreamEvent = Union[
    tuple[Literal["token"], str],
    tuple[Literal["manual_checkpoint"], dict],
    tuple[Literal["done"], dict, str],
]


class ResponseService:
    async def generate(self, session: SessionRecord) -> tuple[dict, str]:
        """그래프를 동기 방식으로 실행하고 (response, intent)를 반환한다.

        호출 전에 사용자 메시지가 session.lc_messages에 추가돼 있어야 한다.
        완료 후 session.lc_messages를 그래프 출력으로 교체한다.
        """
        from graph.graph import graph

        result = await graph.ainvoke(
            {
                "session_id": session.id,
                "messages": list(session.lc_messages),
                "intent": None,
                "response": {},
                "menu_results": session.menu_results,
                "cs_results": session.cs_results,
                "selected_order": session.selected_order,
                "last_menu_query": session.last_menu_query,
                "shown_menu_names": session.shown_menu_names,
            }
        )

        session.lc_messages = list(result["messages"])
        session.menu_results = result.get("menu_results") or session.menu_results
        session.cs_results = result.get("cs_results") or session.cs_results
        session.last_menu_query = result.get("last_menu_query") or session.last_menu_query
        session.shown_menu_names = (
            result.get("shown_menu_names") or session.shown_menu_names
        )
        session.selected_order = None

        response = result.get("response", {"type": "text", "message": ""})
        intent: str = result.get("intent") or "unknown"
        return response, intent

    async def generate_stream(
        self, session: SessionRecord
    ) -> AsyncIterator[StreamEvent]:
        """그래프 스트리밍 이벤트를 yield한다.

        yields:
            ("token", token_text)           — 생성 중인 LLM 토큰
            ("done", response_dict, intent) — 완료 시 최종 응답과 의도
        """
        from graph.graph import graph

        initial_state = {
            "session_id": session.id,
            "messages": list(session.lc_messages),
            "intent": None,
            "response": {},
            "menu_results": session.menu_results,
            "cs_results": session.cs_results,
            "selected_order": session.selected_order,
            "last_menu_query": session.last_menu_query,
            "shown_menu_names": session.shown_menu_names,
        }

        final_response: dict = {}
        final_intent: str = "unknown"
        final_lc_messages = list(session.lc_messages)
        final_menu_results = session.menu_results
        final_cs_results = session.cs_results
        final_last_menu_query = session.last_menu_query
        final_shown_menu_names = session.shown_menu_names

        graph_events: asyncio.Queue = asyncio.Queue()
        checkpoint_listener = manual_checkpoint_broker.listen(session.id)

        async def consume_graph_events() -> None:
            try:
                async for event in graph.astream_events(initial_state, version="v2"):
                    await graph_events.put(event)
                await graph_events.put({"event": "__graph_done__"})
            except Exception as exc:
                await graph_events.put({"event": "__graph_error__", "error": exc})

        def drain_checkpoints() -> list[dict]:
            checkpoints: list[dict] = []
            while True:
                try:
                    event = checkpoint_listener.get_nowait()
                except queue.Empty:
                    break
                checkpoint = event.get("checkpoint")
                if checkpoint:
                    checkpoints.append(checkpoint)
            return checkpoints

        graph_task = asyncio.create_task(consume_graph_events())
        try:
            graph_done = False
            while not graph_done:
                for checkpoint in drain_checkpoints():
                    yield ("manual_checkpoint", checkpoint)

                try:
                    event = await asyncio.wait_for(graph_events.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                for checkpoint in drain_checkpoints():
                    yield ("manual_checkpoint", checkpoint)

                kind = event["event"]
                if kind == "__graph_done__":
                    graph_done = True
                    continue
                if kind == "__graph_error__":
                    raise event["error"]

                if kind == "on_chat_model_stream":
                    node = event.get("metadata", {}).get("langgraph_node", "")
                    if node in ("menu_agent", "cs_agent", "fallback"):
                        chunk = event["data"]["chunk"]
                        if chunk.content:
                            yield ("token", chunk.content)

                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event["data"].get("output", {})
                    final_response = output.get("response", {})
                    final_intent = output.get("intent") or "unknown"
                    final_lc_messages = list(output.get("messages", []))
                    final_menu_results = output.get("menu_results", final_menu_results)
                    final_cs_results = output.get("cs_results", final_cs_results)
                    final_last_menu_query = output.get(
                        "last_menu_query", final_last_menu_query
                    )
                    final_shown_menu_names = output.get(
                        "shown_menu_names", final_shown_menu_names
                    )

            for checkpoint in drain_checkpoints():
                yield ("manual_checkpoint", checkpoint)
        finally:
            manual_checkpoint_broker.unlisten(session.id, checkpoint_listener)
            if not graph_task.done():
                graph_task.cancel()

        session.lc_messages = final_lc_messages
        session.menu_results = final_menu_results
        session.cs_results = final_cs_results
        session.last_menu_query = final_last_menu_query
        session.shown_menu_names = final_shown_menu_names
        session.selected_order = None

        yield ("done", final_response, final_intent)

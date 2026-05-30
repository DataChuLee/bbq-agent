"""
Small manual test client for the BBQ LangGraph app.

Examples:
    venv\\Scripts\\python.exe test_graph.py
    venv\\Scripts\\python.exe test_graph.py --order-smoke
"""

from __future__ import annotations

import argparse
import asyncio

from langchain_core.messages import HumanMessage

from graph.graph import graph


DEFAULT_ORDER_PROMPT = (
    "\ud669\uae08\uc62c\ub9ac\ube0c \uce58\ud0a8\uc5d0 "
    "\ucf5c\ub77c 1.25L \uc635\uc158\uc73c\ub85c "
    "\ubc30\ub2ec \uc8fc\ubb38\ud560\uac8c. "
    "BBQ \uc7a5\ubc14\uad6c\ub2c8\uc5d0 \ub2f4\uc544\uc918."
)


async def run(user_input: str, history: list, cache: dict) -> tuple[dict, list, dict]:
    history.append(HumanMessage(content=user_input))
    result = await graph.ainvoke(
        {
            "messages": history,
            "intent": None,
            "response": {},
            "menu_results": cache.get("menu_results"),
            "cs_results": cache.get("cs_results"),
        }
    )
    history = list(result["messages"])
    cache["menu_results"] = result.get("menu_results", cache.get("menu_results"))
    cache["cs_results"] = result.get("cs_results", cache.get("cs_results"))
    return result["response"], history, cache


async def run_order_smoke(prompt: str = DEFAULT_ORDER_PROMPT) -> dict:
    history = []
    cache = {"menu_results": {}, "cs_results": {}}
    response, _history, _cache = await run(prompt, history, cache)
    return response


def print_response(response: dict) -> None:
    print(f"Bot [{response.get('type')}]: ", end="")
    if response.get("type") == "menu_cards":
        for item in response.get("items", []):
            print(f"\n  - {item['name']} ({item['category']}) {item['price']}")
    else:
        print(response.get("message") or response.get("question", ""))
    print()


async def interactive_main() -> None:
    print("=== BBQ Graph manual test (quit: q) ===\n")
    history = []
    cache = {"menu_results": {}, "cs_results": {}}
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "q":
            break
        if not user_input:
            continue
        response, history, cache = await run(user_input, history, cache)
        print_response(response)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BBQ LangGraph test client.")
    parser.add_argument(
        "--order-smoke",
        action="store_true",
        help="Run one order-preparation graph smoke test with browser-use.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_ORDER_PROMPT,
        help="Prompt to use with --order-smoke.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.order_smoke:
        print_response(asyncio.run(run_order_smoke(args.prompt)))
    else:
        asyncio.run(interactive_main())


if __name__ == "__main__":
    main()

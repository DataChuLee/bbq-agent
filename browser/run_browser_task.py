from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
VENV_SCRIPTS = ROOT / ".venv" / "Scripts"
DEFAULT_MODEL = "gpt-4.1-mini"


async def _click_element_by_prompt(page, llm, prompt: str) -> None:
    element = await page.must_get_element_by_prompt(prompt, llm=llm)
    await element.click()


async def _page_inner_text(page) -> str:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return ""

    result = await evaluate("() => document.body ? document.body.innerText : ''")
    return str(result or "")


def _normalize_visible_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def _missing_visible_options(
    expected_options: list[str], visible_text: str
) -> list[str]:
    normalized_visible_text = _normalize_visible_text(visible_text)
    return [
        option
        for option in expected_options
        if _normalize_visible_text(option)
        and _normalize_visible_text(option) not in normalized_visible_text
    ]


def _build_bbq_order_tools(Tools, ActionResult, BrowserSession, llm):
    tools = Tools()
    clicked_add_to_cart_buttons: set[str] = set()

    async def click_exact_bbq_menu_item(menu_name, browser_session):
        if not str(menu_name or "").strip():
            return ActionResult(error="menu_name is required")

        page = await browser_session.get_current_page()
        await _click_element_by_prompt(
            page,
            llm,
            (
                "the single BBQ menu card or button whose visible text exactly "
                f"matches this full menu name: {menu_name}. Do not choose a prefix, "
                "family item, visually similar item, or nearby menu."
            ),
        )
        return ActionResult(
            extracted_content=f"Clicked exact BBQ menu item: {menu_name}",
            long_term_memory=f"Exact BBQ menu item clicked: {menu_name}",
        )

    click_exact_bbq_menu_item.__annotations__ = {
        "menu_name": str,
        "browser_session": BrowserSession,
        "return": ActionResult,
    }
    tools.action(
        "Click the exact BBQ menu item by full visible name",
        allowed_domains=["*.bbq.co.kr", "bbq.co.kr"],
    )(click_exact_bbq_menu_item)

    async def click_exact_bbq_option(option_name, group_name, browser_session):
        if not str(option_name or "").strip():
            return ActionResult(error="option_name is required")

        group_text = str(group_name or "the matching option group").strip()
        page = await browser_session.get_current_page()
        await _click_element_by_prompt(
            page,
            llm,
            (
                f"the exact option '{option_name}' inside option group '{group_text}'. "
                "Treat whitespace-only differences as equal, but do not choose a "
                "similar, cheaper, more expensive, default, or nearby option."
            ),
        )
        return ActionResult(
            extracted_content=f"Clicked exact BBQ option: {group_text} -> {option_name}",
            long_term_memory=f"Exact BBQ option clicked: {group_text} -> {option_name}",
        )

    click_exact_bbq_option.__annotations__ = {
        "option_name": str,
        "group_name": str,
        "browser_session": BrowserSession,
        "return": ActionResult,
    }
    tools.action(
        "Click an exact BBQ option within its option group",
        allowed_domains=["*.bbq.co.kr", "bbq.co.kr"],
    )(click_exact_bbq_option)

    async def click_exact_bbq_order_type(order_type, browser_session):
        if not str(order_type or "").strip():
            return ActionResult(error="order_type is required")

        page = await browser_session.get_current_page()
        await _click_element_by_prompt(
            page,
            llm,
            f"the order type control labeled exactly '{order_type}'",
        )
        return ActionResult(
            extracted_content=f"Clicked BBQ order type: {order_type}",
            long_term_memory=f"BBQ order type clicked: {order_type}",
        )

    click_exact_bbq_order_type.__annotations__ = {
        "order_type": str,
        "browser_session": BrowserSession,
        "return": ActionResult,
    }
    tools.action(
        "Click the exact BBQ order type",
        allowed_domains=["*.bbq.co.kr", "bbq.co.kr"],
    )(click_exact_bbq_order_type)

    async def click_bbq_add_to_cart_after_visible_options(
        expected_options, button_label, browser_session
    ):
        expected = [str(option).strip() for option in (expected_options or [])]
        normalized_button_label = _normalize_visible_text(button_label)
        if normalized_button_label in clicked_add_to_cart_buttons:
            return ActionResult(
                extracted_content=(
                    f"Already clicked BBQ add-to-cart button '{button_label}'. "
                    "Do not click it again. Move to cart or stop if the cart is ready."
                ),
                long_term_memory=(
                    f"Duplicate BBQ add-to-cart click refused: {button_label}"
                ),
            )

        page = await browser_session.get_current_page()
        visible_text = await _page_inner_text(page)
        missing_options = _missing_visible_options(expected, visible_text)
        if missing_options:
            return ActionResult(
                error=(
                    "Refused to add to cart because these selected options were "
                    f"not visible on the page: {', '.join(missing_options)}"
                ),
                extracted_content=(
                    "Missing selected options before add-to-cart: "
                    + ", ".join(missing_options)
                ),
            )

        await _click_element_by_prompt(
            page,
            llm,
            (
                f"the visible BBQ button labeled exactly '{button_label}'. "
                "Do not click payment, checkout, order completion, or final confirmation."
            ),
        )
        clicked_add_to_cart_buttons.add(normalized_button_label)
        return ActionResult(
            extracted_content=(
                f"Clicked BBQ add-to-cart button '{button_label}' after visible option check."
            ),
            long_term_memory=(
                f"BBQ add-to-cart clicked after option visibility check: {button_label}"
            ),
        )

    click_bbq_add_to_cart_after_visible_options.__annotations__ = {
        "expected_options": list[str],
        "button_label": str,
        "browser_session": BrowserSession,
        "return": ActionResult,
    }
    tools.action(
        "Click BBQ add-to-cart only after selected options are visible",
        allowed_domains=["*.bbq.co.kr", "bbq.co.kr"],
    )(click_bbq_add_to_cart_after_visible_options)

    async def click_bbq_move_to_cart(browser_session):
        page = await browser_session.get_current_page()
        await _click_element_by_prompt(
            page,
            llm,
            (
                "the visible BBQ button labeled exactly '장바구니로 이동하기'. "
                "Do not click payment, checkout, order completion, or final confirmation."
            ),
        )
        return ActionResult(
            extracted_content="Clicked BBQ move-to-cart button.",
            long_term_memory="BBQ move-to-cart button clicked.",
        )

    click_bbq_move_to_cart.__annotations__ = {
        "browser_session": BrowserSession,
        "return": ActionResult,
    }
    tools.action(
        "Click BBQ move-to-cart only after add-to-cart",
        allowed_domains=["*.bbq.co.kr", "bbq.co.kr"],
    )(click_bbq_move_to_cart)

    return tools


def configure_environment() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault(
        "BROWSER_USE_CONFIG_DIR", str(ROOT / ".config" / "browseruse")
    )
    os.environ.setdefault("BROWSER_USE_HOME", str(ROOT / ".browser-use"))
    os.environ["PATH"] = f"{VENV_SCRIPTS}{os.pathsep}{os.environ.get('PATH', '')}"

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(ROOT / ".env", override=False)


async def run_browser_task(
    task: str,
    model: str,
    max_steps: int,
    headless: bool,
    resume_task: str | None = None,
    manual_checkpoint: str | None = None,
    keep_open_on_completion: bool = False,
) -> dict:
    from browser_use import ActionResult, Agent, BrowserSession, ChatOpenAI, Tools

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "ok": False,
            "error": "OPENAI_API_KEY was not found",
            "result": "",
        }

    browser = BrowserSession(headless=headless, keep_alive=True)
    try:
        llm = ChatOpenAI(model=model)
        tools = _build_bbq_order_tools(Tools, ActionResult, BrowserSession, llm)
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser,
            tools=tools,
            use_vision=True,
            use_judge=False,
            enable_planning=False,
            max_actions_per_step=1,
        )

        with contextlib.redirect_stdout(sys.stderr):
            history = await agent.run(max_steps=max_steps)

        if resume_task:
            if manual_checkpoint:
                print(f"\n{manual_checkpoint}", file=sys.stderr)
                print(
                    "Press Enter after completing this step in the browser...",
                    file=sys.stderr,
                )
                input()

            resume_agent = Agent(
                task=resume_task,
                llm=llm,
                browser_session=browser,
                tools=tools,
                use_vision=True,
                use_judge=False,
                enable_planning=False,
                max_actions_per_step=1,
            )
            with contextlib.redirect_stdout(sys.stderr):
                history = await resume_agent.run(max_steps=max_steps)

        return {
            "ok": bool(history.is_done()),
            "result": history.final_result() or "",
            "done": bool(history.is_done()),
            "current_url": _latest_history_url(history),
        }
    finally:
        if not (keep_open_on_completion and not headless):
            await browser.stop()


def _latest_history_url(history) -> str:
    urls = getattr(history, "urls", None)
    if not callable(urls):
        return ""

    for url in reversed(urls()):
        if url:
            return str(url)
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one browser-use task.")
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--model",
        default=os.getenv("BROWSER_USE_LLM_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--keep-open-on-completion", action="store_true")
    parser.add_argument("--resume-task")
    parser.add_argument("--manual-checkpoint")
    return parser.parse_args()


def main() -> int:
    configure_environment()
    args = parse_args()

    try:
        payload = asyncio.run(
            run_browser_task(
                task=args.task,
                model=args.model,
                max_steps=args.max_steps,
                headless=not args.headed,
                resume_task=args.resume_task,
                manual_checkpoint=args.manual_checkpoint,
                keep_open_on_completion=args.keep_open_on_completion,
            )
        )
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload.get("ok") else 2
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "result": ""}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

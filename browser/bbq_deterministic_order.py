from __future__ import annotations

import inspect
import sys
from typing import Any


BBQ_URL = "https://www.bbq.co.kr"

ORDER_TYPE_LABELS = {
    "delivery": "배달",
    "pickup": "포장",
}

POPUP_CLOSE_LABELS = (
    "오늘 그만보기",
    "닫기",
    "Close",
    "X",
)

ADD_TO_CART_LABELS = (
    "주문서에 담기",
    "장바구니 담기",
)

MOVE_TO_CART_LABEL = "장바구니로 이동하기"


class DeterministicOrderError(Exception):
    allow_fallback = False

    def __init__(
        self,
        message: str,
        *,
        current_url: str = "",
        fallback_stage: str = "full",
    ) -> None:
        super().__init__(message)
        self.current_url = current_url
        self.fallback_stage = fallback_stage

    def to_payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": str(self),
            "result": "",
            "done": False,
            "current_url": self.current_url,
        }


class DeterministicNavigationError(DeterministicOrderError):
    allow_fallback = True


class DeterministicSelectionError(DeterministicOrderError):
    allow_fallback = False


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_visible_text(value: str) -> str:
    return "".join(str(value or "").split()).lower()


def _option_detail_for(
    option_name: str,
    option_details: list[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_option = _normalize_visible_text(option_name)
    for detail in option_details:
        detail_option = str(detail.get("option_name") or "").strip()
        if _normalize_visible_text(detail_option) == normalized_option:
            return detail
    return None


async def _goto(page: Any, url: str) -> None:
    goto = getattr(page, "goto", None)
    if not callable(goto):
        raise DeterministicNavigationError("current page does not support goto")
    await _maybe_await(goto(url))


async def _page_inner_text(page: Any) -> str:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return ""
    result = await _maybe_await(
        evaluate("() => document.body ? document.body.innerText : ''")
    )
    return str(result or "")


async def _click_by_locator_text(page: Any, text: str) -> bool:
    get_by_text = getattr(page, "get_by_text", None)
    if not callable(get_by_text):
        return False

    locator = get_by_text(text, exact=True)
    count = await _maybe_await(locator.count())
    if not count:
        return False

    first = locator.first()
    await _maybe_await(first.click())
    return True


async def _click_by_dom_text(page: Any, text: str) -> bool:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return False

    script = r"""(targetText) => {
      const normalize = (value) => String(value || '').replace(/\s+/g, '').toLowerCase();
      const target = normalize(targetText);
      const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      };
      const clickableFor = (element) => {
        return element.closest('button,a,label,[role="button"],li,div') || element;
      };
      const elements = Array.from(document.querySelectorAll('button,a,label,[role="button"],span,p,li,div'));
      for (const element of elements) {
        if (!isVisible(element)) continue;
        const ownText = normalize(element.innerText || element.textContent || '');
        if (ownText !== target) continue;
        clickableFor(element).click();
        return true;
      }
      return false;
    }
    """
    try:
        result = await _maybe_await(evaluate(script, text))
    except TypeError:
        return False
    if isinstance(result, str):
        return result.strip().lower() == "true"
    return bool(result)


async def _click_option_in_group_by_dom(
    page: Any,
    option_name: str,
    group_name: str,
) -> bool:
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return False

    script = r"""(optionName, groupName) => {
      const normalize = (value) => String(value || '').replace(/\s+/g, '').toLowerCase();
      const optionTarget = normalize(optionName);
      const groupTarget = normalize(groupName);
      const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      };
      const clickableFor = (element) => {
        return element.closest('button,a,label,[role="button"],li,div') || element;
      };
      const exactTextElements = Array.from(document.querySelectorAll('button,a,label,[role="button"],span,p,li,div'));
      const groups = exactTextElements.filter((element) => {
        if (!isVisible(element)) return false;
        return normalize(element.innerText || element.textContent || '') === groupTarget;
      });
      for (const group of groups) {
        let container = group;
        for (let depth = 0; depth < 5 && container; depth += 1) {
          const options = Array.from(container.querySelectorAll('button,a,label,[role="button"],span,p,li,div'));
          for (const option of options) {
            if (!isVisible(option)) continue;
            if (normalize(option.innerText || option.textContent || '') !== optionTarget) continue;
            clickableFor(option).click();
            return true;
          }
          container = container.parentElement;
        }
      }
      return false;
    }"""
    try:
        result = await _maybe_await(evaluate(script, option_name, group_name))
    except TypeError:
        return False
    if isinstance(result, str):
        return result.strip().lower() == "true"
    return bool(result)


async def _click_option_in_group(
    page: Any,
    option_name: str,
    group_name: str,
) -> bool:
    custom_click = getattr(page, "click_exact_option", None)
    if callable(custom_click):
        clicked = await _maybe_await(custom_click(option_name, group_name))
        if clicked:
            return True

    return await _click_option_in_group_by_dom(page, option_name, group_name)


async def _click_exact_text(
    page: Any,
    text: str,
    *,
    error_cls: type[DeterministicOrderError] = DeterministicSelectionError,
) -> None:
    if not str(text or "").strip():
        return

    custom_click = getattr(page, "click_exact_text", None)
    if callable(custom_click) and await _maybe_await(custom_click(text)):
        return

    if await _click_by_locator_text(page, text):
        return

    if await _click_by_dom_text(page, text):
        return

    raise error_cls(f"exact visible text was not found: {text}")


async def _click_option(
    page: Any,
    option_name: str,
    option_details: list[dict[str, Any]],
) -> None:
    detail = _option_detail_for(option_name, option_details)
    group_name = str((detail or {}).get("group_name") or "").strip()
    if group_name and group_name != "unknown group":
        if await _click_option_in_group(page, option_name, group_name):
            return
        raise DeterministicSelectionError(
            f"exact option was not found in group: {group_name} -> {option_name}"
        )

    await _click_exact_text(page, option_name)


async def _click_optional_texts(page: Any, labels: tuple[str, ...]) -> None:
    for label in labels:
        try:
            await _click_exact_text(
                page,
                label,
                error_cls=DeterministicNavigationError,
            )
        except DeterministicOrderError:
            continue


async def _click_first_available(
    page: Any,
    labels: tuple[str, ...],
    *,
    error_cls: type[DeterministicOrderError],
) -> str:
    last_error: DeterministicOrderError | None = None
    for label in labels:
        try:
            await _click_exact_text(page, label, error_cls=error_cls)
            return label
        except DeterministicOrderError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise error_cls("no labels were provided")


def _missing_visible_options(expected_options: list[str], visible_text: str) -> list[str]:
    normalized_visible = _normalize_visible_text(visible_text)
    return [
        option
        for option in expected_options
        if _normalize_visible_text(option)
        and _normalize_visible_text(option) not in normalized_visible
    ]


async def _current_url(browser_session: Any, page: Any) -> str:
    get_current_page_url = getattr(browser_session, "get_current_page_url", None)
    if callable(get_current_page_url):
        url = await _maybe_await(get_current_page_url())
        if url:
            return str(url)
    return str(getattr(page, "url", "") or "")


def _wait_for_manual_checkpoint(manual_checkpoint: str | None) -> None:
    if not manual_checkpoint:
        return
    print(f"\n{manual_checkpoint}", file=sys.stderr)
    print("Press Enter after completing this step in the browser...", file=sys.stderr)
    input()


async def run_deterministic_order(
    *,
    browser_session: Any,
    order: dict[str, Any],
    manual_checkpoint: str | None = None,
) -> dict[str, Any]:
    """Prepare a BBQ order with deterministic page actions."""
    page = await browser_session.get_current_page()
    menu_name = str(order.get("menu_name") or "").strip()
    menu_category = str(order.get("menu_category") or "").strip()
    options = [str(option).strip() for option in (order.get("options") or [])]
    options = [option for option in options if option]
    option_details = [
        detail
        for detail in (order.get("option_details") or [])
        if isinstance(detail, dict)
    ]
    order_type = str(order.get("order_type") or "").strip()
    order_type_label = ORDER_TYPE_LABELS.get(order_type, order_type)

    await _goto(page, BBQ_URL)
    await _click_optional_texts(page, POPUP_CLOSE_LABELS)
    await _click_exact_text(
        page,
        order_type_label,
        error_cls=DeterministicNavigationError,
    )
    _wait_for_manual_checkpoint(manual_checkpoint)

    try:
        await _click_exact_text(page, "메뉴", error_cls=DeterministicNavigationError)
        await _click_exact_text(
            page,
            menu_category,
            error_cls=DeterministicNavigationError,
        )
    except DeterministicNavigationError as exc:
        raise DeterministicNavigationError(
            str(exc),
            current_url=await _current_url(browser_session, page),
            fallback_stage="resume",
        ) from exc
    await _click_exact_text(page, menu_name)
    missing_options: list[str] = []
    for option in options:
        try:
            await _click_option(page, option, option_details)
        except DeterministicSelectionError:
            missing_options.append(option)

    if missing_options:
        return {
            "ok": True,
            "result": "Selected options are missing",
            "done": False,
            "missing_options": missing_options,
            "current_url": await _current_url(browser_session, page),
        }

    await _click_exact_text(page, order_type_label)
    visible_text = await _page_inner_text(page)
    missing_options = _missing_visible_options(options, visible_text)
    if missing_options:
        return {
            "ok": True,
            "result": "Selected options are missing",
            "done": False,
            "missing_options": missing_options,
            "current_url": await _current_url(browser_session, page),
        }

    await _click_first_available(
        page,
        ADD_TO_CART_LABELS,
        error_cls=DeterministicSelectionError,
    )
    try:
        await _click_exact_text(page, MOVE_TO_CART_LABEL)
    except DeterministicSelectionError:
        pass

    return {
        "ok": True,
        "result": "Cart is ready",
        "done": True,
        "current_url": await _current_url(browser_session, page),
    }

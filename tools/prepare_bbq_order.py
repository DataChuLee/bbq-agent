from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from api.services.manual_checkpoint import manual_checkpoint_broker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BROWSER_DIR = PROJECT_ROOT / "browser"
BROWSER_PYTHON = BROWSER_DIR / ".venv" / "Scripts" / "python.exe"
BROWSER_RUNNER = BROWSER_DIR / "run_browser_task.py"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_STEPS = 20
DEFAULT_MODEL = "gpt-4.1-mini"
BBQ_URL = "https://www.bbq.co.kr"
MANUAL_CHECKPOINT_MESSAGE = (
    "브라우저에서 BBQ 로그인과 주소 입력/검색/선택을 직접 완료하세요. "
    "완료 후 이 화면의 계속 버튼을 누르면 주문 준비를 이어갑니다."
)
MENU_VARIANT_TERMS = ("핫크리스피",)
POPUP_CLOSE_INSTRUCTION = (
    "Close any popup, promotion modal, coupon modal, image banner, or overlay before "
    "continuing. Prefer visible controls labeled '오늘 그만보기', '닫기', 'Close', 'X', or "
    "the top-right close button. If both '오늘 그만보기' and '닫기' are visible, click "
    "'오늘 그만보기' first, then '닫기'."
)


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["BROWSER_USE_CONFIG_DIR"] = str(BROWSER_DIR / ".config" / "browseruse")
    env["BROWSER_USE_HOME"] = str(BROWSER_DIR / ".browser-use")
    env["PATH"] = (
        f"{BROWSER_DIR / '.venv' / 'Scripts'}{os.pathsep}{env.get('PATH', '')}"
    )
    return env


def _failure(error: str, **extra: str) -> str:
    payload: dict[str, object] = {"ok": False, "error": error, "result": ""}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _loads_runner_payload(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index in range(len(stdout) - 1, -1, -1):
        if stdout[index] != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stdout[index:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    raise json.JSONDecodeError("no JSON object found", stdout, 0)


def _normalize_option_text(value: str) -> str:
    return "".join(value.split()).lower()


def _build_option_instruction_details(
    options: list[str],
    option_details: list[dict[str, Any]] | None,
) -> str:
    if option_details:
        lines = []
        for detail in option_details:
            option_name = str(detail.get("option_name") or "").strip()
            if not option_name:
                continue
            group_name = str(detail.get("group_name") or "unknown group")
            required = "required" if detail.get("required") else "optional"
            add_price = detail.get("add_price", 0)
            compact = "".join(option_name.split())
            lines.append(
                "- "
                f"{group_name} -> {option_name} "
                f"({required}, add_price={add_price}, compact={compact}, "
                f"normalized={_normalize_option_text(option_name)})"
            )
        if lines:
            return "\n".join(lines)

    if options:
        return "\n".join(
            f"- unknown group -> {option} "
            f"(compact={''.join(option.split())}, normalized={_normalize_option_text(option)})"
            for option in options
        )

    return "- no extra options"


def _order_status_from_result(result: str) -> str:
    normalized = result.lower()
    option_review_markers = (
        "option is unavailable",
        "option is ambiguous",
        "option unavailable",
        "ambiguous option",
        "missing option",
        "not selected",
        "없",
        "모호",
    )
    if any(marker in normalized for marker in option_review_markers):
        return "option_review"
    return "cart_ready"


def _next_action_for_status(status: str) -> str:
    if status == "option_review":
        return "BBQ 공식 사이트에서 옵션을 확인한 뒤 장바구니에 담아 주세요."
    return "BBQ 공식 사이트에서 장바구니와 결제를 확인해 주세요."


def _message_for_order_status(status: str, menu_name: str) -> str:
    display_name = menu_name.strip() or "선택한 메뉴"
    if status == "option_review":
        return f"{display_name}의 옵션 확인이 필요해요."
    return f"{display_name}이 장바구니에 담겼어요."


def _build_order_status_payload(
    runner_payload: dict,
    menu_name: str,
    options: list[str],
    order_type: str,
) -> dict[str, object]:
    result = str(runner_payload.get("result") or "")
    missing_options = runner_payload.get("missing_options") or []
    status = "option_review" if missing_options else _order_status_from_result(result)
    return {
        "ok": True,
        "type": "order_status",
        "status": status,
        "message": _message_for_order_status(status, menu_name),
        "menu_name": menu_name,
        "expected_options": options,
        "selected_options": runner_payload.get("selected_options") or [],
        "missing_options": missing_options,
        "order_type": order_type,
        "current_url": str(runner_payload.get("current_url") or ""),
        "next_action": _next_action_for_status(status),
    }


def _read_stream(stream, chunks: list[str]) -> None:
    if stream is None:
        return

    while True:
        chunk = stream.readline()
        if not chunk:
            break
        chunks.append(chunk)


def _read_stderr_and_publish_checkpoint(
    stream,
    chunks: list[str],
    process,
    session_id: str,
    manual_checkpoint: str,
    timeout: int,
) -> None:
    if stream is None:
        return

    checkpoint_sent = False
    while True:
        chunk = stream.readline()
        if not chunk:
            break
        chunks.append(chunk)
        if not session_id or checkpoint_sent or manual_checkpoint not in chunk:
            continue

        checkpoint_sent = True
        checkpoint = manual_checkpoint_broker.publish(session_id, manual_checkpoint)
        if not checkpoint.resume_event.wait(timeout=timeout):
            manual_checkpoint_broker.clear(session_id, checkpoint.run_id)
            process.kill()
            return

        if process.stdin is not None:
            process.stdin.write("\n")
            process.stdin.flush()


def _run_browser_runner_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    session_id: str,
    manual_checkpoint: str,
    popen_factory=subprocess.Popen,
) -> subprocess.CompletedProcess:
    process = popen_factory(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_thread = threading.Thread(
        target=_read_stream,
        args=(process.stdout, stdout_chunks),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_stderr_and_publish_checkpoint,
        args=(
            process.stderr,
            stderr_chunks,
            process,
            session_id,
            manual_checkpoint,
            timeout,
        ),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        raise

    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)

    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
    )


def _build_exact_menu_warning(menu_name: str) -> str:
    for term in MENU_VARIANT_TERMS:
        if term not in menu_name:
            continue

        shorter_name = menu_name.replace(term, "").strip()
        if shorter_name and shorter_name != menu_name:
            return (
                f"Do not select {shorter_name} when the selected menu is {menu_name}."
            )

    return (
        "Do not select a shorter prefix match, broader family item, or visually similar "
        f"menu when the selected menu is {menu_name}."
    )


def _build_order_task(menu_name: str, options: list[str], order_type: str) -> str:
    return _build_order_task_with_category(menu_name, options, order_type, "")


def _build_order_task_with_category(
    menu_name: str, options: list[str], order_type: str, menu_category: str
) -> str:
    option_text = ", ".join(options) if options else "no extra options"
    category_text = menu_category or "unknown"
    return f"""
Open {BBQ_URL} in a visible browser and prepare the login/address step for a BBQ order.

Menu to select after the manual checkpoint: {menu_name}
Menu category tab after the manual checkpoint: {category_text}
Options to select after the manual checkpoint: {option_text}
Order type to use after the manual checkpoint: {order_type}

Process:
1. Go to the BBQ website.
2. {POPUP_CLOSE_INSTRUCTION}
3. Navigate only until login, address search, address selection, or store/location
   selection requires user input.
4. Do not type credentials, do not guess the address, and do not select a random address.
5. Do not search for, select, configure, or add any menu item before the manual checkpoint.
6. Stop once the user needs to manually log in, enter/select address, or confirm location.
7. Return a short Korean message telling the user to complete that step in the open browser.
""".strip()


def _build_order_resume_task(
    menu_name: str, options: list[str], order_type: str
) -> str:
    return _build_order_resume_task_with_category(menu_name, options, order_type, "")


def _build_order_resume_task_with_category(
    menu_name: str,
    options: list[str],
    order_type: str,
    menu_category: str,
    option_details: list[dict[str, Any]] | None = None,
) -> str:
    option_text = ", ".join(options) if options else "no extra options"
    option_detail_text = _build_option_instruction_details(options, option_details)
    category_text = menu_category or "unknown"
    return f"""
Continue the BBQ order from the current browser page after the user manually completed
login/address/location selection.

Selected menu: {menu_name}
Menu category tab: {category_text}
Selected options: {option_text}
Selected option details:
{option_detail_text}
Order type: {order_type}
Exact selected menu name: {menu_name}
Exact menu selection rule: Choose the exact full menu name. {_build_exact_menu_warning(menu_name)}

Critical click policy:
- Use the custom tool named "Click the exact BBQ menu item by full visible name" for selecting the menu item.
- Use the custom tool named "Click an exact BBQ option within its option group" for every requested option.
- Use the custom tool named "Click the exact BBQ order type" for the requested order type.
- Use the custom tool named "Click BBQ add-to-cart only after selected options are visible" with button_label='주문서에 담기' for '주문서에 담기'.
- Use the custom tool named "Click BBQ add-to-cart only after selected options are visible" with button_label='장바구니 담기' for '장바구니 담기'.
- Never call the same add-to-cart button_label more than once for the same order.
- Use the custom tool named "Click BBQ move-to-cart only after add-to-cart" for '장바구니로 이동하기'.
- Do not use the default click action for the menu item, requested options, order type, add-to-cart, move-to-cart, payment, checkout, or final order confirmation.

Process:
1. Continue from the current browser state.
2. {POPUP_CLOSE_INSTRUCTION}
3. Click the top navigation item labeled '메뉴' before looking for category tabs.
   The menu categories are shown after entering the menu section.
4. Click the menu category tab labeled '{category_text}' before looking for the menu.
   BBQ does not provide a menu-name search box, so use the horizontal category tabs
   such as 신메뉴, 세트메뉴, 후라이드, 양념, 반반, 시즈닝, 구이, or 1인분 메뉴.
   If the tab is not visible, scroll the category bar horizontally or use the arrow/dropdown.
5. Find and click the exact selected menu within that category: {menu_name}.
   Use the custom tool named "Click the exact BBQ menu item by full visible name".
   If the exact full menu name is unavailable, stop and report that instead of choosing a similar item.
6. Click exactly these requested options: {option_text}.
   Use the custom tool named "Click an exact BBQ option within its option group" for each option.
   Use these option details to match the correct option group and label:
   {option_detail_text}
   For every selected option, find the option group first, then click the exact option in that group.
   Treat whitespace-only differences as equal, so "Coke 1.25L" and "Coke1.25L" match.
   Use each option's normalized value above to compare labels when the site omits spaces.
   Do not click any option that is not listed above.
7. Before adding to cart, verify every selected option is visibly selected in the option screen
   or appears in the order summary. If any selected option is not selected, do not add to cart.
8. If an option is unavailable or ambiguous, stop on the option selection page and report the issue.
   Do not choose a visually similar, cheaper, more expensive, default, or nearby option.
9. Click the requested order type exactly: {order_type}.
   Use the custom tool named "Click the exact BBQ order type".
10. Click the button labeled '주문서에 담기' if it appears after option selection.
    Use the custom tool named "Click BBQ add-to-cart only after selected options are visible" with button_label='주문서에 담기'.
11. Then click the button labeled '장바구니 담기' if it appears.
    Use the custom tool named "Click BBQ add-to-cart only after selected options are visible" with button_label='장바구니 담기'.
12. Then click the button labeled '장바구니로 이동하기' and wait until the cart page is loaded.
    Use the custom tool named "Click BBQ move-to-cart only after add-to-cart".
13. Stop only after the current page is the cart page.
14. Do not submit payment. Do not click the final payment/checkout confirmation button.
15. Return a short Korean summary and include the current cart page URL exactly. If options are missing,
include the missing option names exactly.
""".strip()


@tool
def prepare_bbq_order(
    menu_name: str,
    options: list[str],
    order_type: str,
    state: Annotated[dict, InjectedState],
    menu_category: str = "",
    option_details: list[dict[str, Any]] | None = None,
) -> str:
    """Open BBQ in browser-use and prepare the selected menu/options for user checkout."""
    if not BROWSER_PYTHON.exists():
        return _failure("browser-use python was not found", path=str(BROWSER_PYTHON))
    if not BROWSER_RUNNER.exists():
        return _failure("browser runner was not found", path=str(BROWSER_RUNNER))

    model = os.getenv("BROWSER_USE_LLM_MODEL", DEFAULT_MODEL)
    max_steps = os.getenv("BBQ_ORDER_MAX_STEPS", str(DEFAULT_MAX_STEPS))
    timeout = int(os.getenv("BBQ_ORDER_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    command = [
        str(BROWSER_PYTHON),
        str(BROWSER_RUNNER),
        "--task",
        _build_order_task_with_category(menu_name, options, order_type, menu_category),
        "--model",
        model,
        "--max-steps",
        max_steps,
        "--headed",
        "--keep-open-on-completion",
        "--manual-checkpoint",
        (
            "브라우저에서 BBQ 로그인과 주소 입력/검색/선택을 직접 완료하세요. "
            "완료 후 이 터미널로 돌아와 Enter를 누르면 주문 준비를 이어갑니다."
        ),
        "--resume-task",
        _build_order_resume_task_with_category(
            menu_name, options, order_type, menu_category, option_details
        ),
    ]
    command[command.index("--manual-checkpoint") + 1] = MANUAL_CHECKPOINT_MESSAGE

    try:
        completed = _run_browser_runner_command(
            command,
            cwd=PROJECT_ROOT,
            env=_build_env(),
            timeout=timeout,
            session_id=str(state.get("session_id") or ""),
            manual_checkpoint=MANUAL_CHECKPOINT_MESSAGE,
        )
    except subprocess.TimeoutExpired:
        return _failure("browser runner timed out")

    stdout = completed.stdout.strip()
    if completed.returncode != 0:
        return _failure(
            "browser runner failed",
            stdout=stdout,
            stderr=(completed.stderr or "").strip(),
        )

    try:
        payload = _loads_runner_payload(stdout)
    except json.JSONDecodeError:
        return _failure(
            "browser runner returned invalid JSON",
            stdout=stdout,
            stderr=(completed.stderr or "").strip(),
        )

    if payload.get("ok"):
        payload = _build_order_status_payload(
            payload,
            menu_name=menu_name,
            options=options,
            order_type=order_type,
        )

    return json.dumps(payload, ensure_ascii=False)

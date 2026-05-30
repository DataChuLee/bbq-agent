from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
VENV_SCRIPTS = ROOT / ".venv" / "Scripts"
DEFAULT_MODEL = "gpt-4.1-mini"
# 비용을 작게 유지하기 위해 기본 태스크는 짧은 공개 페이지에서 제목만 읽습니다.
DEFAULT_TASK = "Open https://example.com, read the page title, then answer with only the title text."


def configure_environment() -> None:
    # browser-use CLI/브라우저가 Windows CP949 출력 문제를 피하도록 UTF-8을 강제합니다.
    os.environ.setdefault("PYTHONUTF8", "1")
    # browser-use가 사용자 홈 대신 이 테스트 폴더 안에 설정/프로필을 저장하게 합니다.
    os.environ.setdefault(
        "BROWSER_USE_CONFIG_DIR", str(ROOT / ".config" / "browseruse")
    )
    os.environ.setdefault("BROWSER_USE_HOME", str(ROOT / ".browser-use"))
    # 내부에서 uvx 같은 실행 파일을 찾을 수 있도록 테스트 전용 venv를 PATH 앞에 둡니다.
    os.environ["PATH"] = f"{VENV_SCRIPTS}{os.pathsep}{os.environ.get('PATH', '')}"

    from dotenv import load_dotenv

    # 프로젝트 루트의 .env에서 OPENAI_API_KEY를 읽습니다.
    load_dotenv(PROJECT_ROOT / ".env")


async def run_llm_test(
    task: str, model: str, max_steps: int, headless: bool, pause_before_close: bool
) -> int:
    from browser_use import Agent, BrowserSession, ChatOpenAI

    # API 키가 없으면 OpenAI 호출 전에 명확한 메시지로 중단합니다.
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY was not found in environment or project .env.",
            file=sys.stderr,
        )
        return 1

    llm = ChatOpenAI(model=model)
    browser = BrowserSession(headless=headless)
    # Agent가 LLM 판단으로 브라우저를 조작합니다. judge/planning/vision은 비용과 단계를 줄이려고 끕니다.
    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser,
        use_vision=False,
        use_judge=False,
        enable_planning=False,
        max_actions_per_step=1,
    )

    try:
        # max_steps가 낮을수록 비용과 실행 시간이 줄지만, 복잡한 사이트에서는 실패할 수 있습니다.
        history = await agent.run(max_steps=max_steps)
        print("\nFinal result:")
        print(history.final_result() or "(no final result)")
        return 0 if history.is_done() else 2
    finally:
        if pause_before_close:
            input(
                "\nBrowser is still open. Press Enter here when you are ready to close it..."
            )
        # 실패해도 브라우저 프로세스가 남지 않도록 항상 종료합니다.
        await browser.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Small browser-use LLM smoke test.")
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK,
        help="Task for the browser-use agent.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("BROWSER_USE_LLM_MODEL", DEFAULT_MODEL),
        help=f"OpenAI model to use. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=4,
        help="Maximum agent steps before stopping.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window instead of running headless.",
    )
    parser.add_argument(
        "--pause-before-close",
        action="store_true",
        help="Wait for Enter before closing the browser so you can inspect it manually.",
    )
    return parser.parse_args()


def main() -> int:
    configure_environment()
    args = parse_args()
    return asyncio.run(
        run_llm_test(
            task=args.task,
            model=args.model,
            max_steps=args.max_steps,
            headless=not args.headed,
            pause_before_close=args.pause_before_close,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

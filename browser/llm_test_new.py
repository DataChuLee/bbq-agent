from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from browser_use import Agent, BrowserSession, ChatOpenAI, ChatOllama


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
VENV_SCRIPTS = ROOT / ".venv" / "Scripts"

# Keep the source file ASCII-safe so the Korean query cannot be corrupted by
# an editor or terminal using a non-UTF-8 code page.
SEARCH_QUERY = "\ub098\uc774\ud0a4 \uba38\ud050\ub9ac\uc5bc \ubca0\uc774\ud37c"
START_URL = "https://crazy11.co.kr/m/"


def configure_environment() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault(
        "BROWSER_USE_CONFIG_DIR", str(ROOT / ".config" / "browseruse")
    )
    os.environ.setdefault("BROWSER_USE_HOME", str(ROOT / ".browser-use"))
    os.environ["PATH"] = f"{VENV_SCRIPTS}{os.pathsep}{os.environ.get('PATH', '')}"
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(ROOT / ".env", override=False)


async def main() -> None:
    configure_environment()

    task = f"""
            구글의 검색한에 'BBQ'를 검색한 다음 접속해줘.
            """

    browser = BrowserSession(headless=False)
    agent = Agent(
        task=task,
        llm=ChatOpenAI(model="gpt-5-nano"),
        browser_session=browser,
        use_vision=False,
        use_judge=False,
        enable_planning=False,
        max_actions_per_step=1,
    )

    try:
        history = await agent.run(max_steps=12)
        print("\nFinal result:")
        print(history.final_result() or "(no final result)")
        input(
            "\nBrowser is still open. Press Enter here when you are ready to close it..."
        )
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())

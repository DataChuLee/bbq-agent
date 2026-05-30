from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_SCRIPTS = ROOT / ".venv" / "Scripts"
BROWSER_USE = VENV_SCRIPTS / "browser-use.exe"
DEFAULT_URL = "https://www.google.com"


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["BROWSER_USE_CONFIG_DIR"] = str(ROOT / ".config" / "browseruse")
    env["BROWSER_USE_HOME"] = str(ROOT / ".browser-use")
    env["PATH"] = f"{VENV_SCRIPTS}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_browser_use(*args: str) -> None:
    command = [str(BROWSER_USE), *args]
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, cwd=ROOT.parent, env=build_env(), check=True)


def main() -> int:
    if not BROWSER_USE.exists():
        print(f"browser-use executable not found: {BROWSER_USE}", file=sys.stderr)
        print("Run: browser\\.venv\\Scripts\\python.exe -m pip install browser-use", file=sys.stderr)
        return 1

    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    try:
        run_browser_use("open", url)
        run_browser_use("state")
    finally:
        run_browser_use("close")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

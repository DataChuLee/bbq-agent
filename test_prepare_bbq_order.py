"""
Manual CLI for testing tools.prepare_bbq_order directly.

Examples:
    venv\\Scripts\\python.exe test_prepare_bbq_order.py --menu "황금올리브"
    venv\\Scripts\\python.exe test_prepare_bbq_order.py --menu "황금올리브" --option "콜라 1.25L" --order-type delivery
"""

from __future__ import annotations

import argparse
import json

from tools.prepare_bbq_order import prepare_bbq_order


DEFAULT_MENU = "\ud669\uae08\uc62c\ub9ac\ube0c"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the prepare_bbq_order tool directly."
    )
    parser.add_argument(
        "--menu",
        default=DEFAULT_MENU,
        help="Final selected BBQ menu name.",
    )
    parser.add_argument(
        "--option",
        action="append",
        default=[],
        help="Selected option. Repeat this flag for multiple options.",
    )
    parser.add_argument(
        "--order-type",
        choices=("delivery", "pickup"),
        default="delivery",
        help="Order type to prepare.",
    )
    return parser.parse_args(argv)


def _pretty_json(raw: str) -> str:
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return raw


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = prepare_bbq_order.func(args.menu, args.option, args.order_type, {})
    print(_pretty_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

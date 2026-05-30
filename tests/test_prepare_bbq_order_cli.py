import json
import unittest
from unittest.mock import patch


class PrepareBbqOrderCliTests(unittest.TestCase):
    def test_parse_args_accepts_menu_options_and_order_type(self) -> None:
        import test_prepare_bbq_order

        args = test_prepare_bbq_order.parse_args(
            [
                "--menu",
                "황금올리브",
                "--option",
                "콜라 1.25L",
                "--option",
                "치즈볼",
                "--order-type",
                "delivery",
            ]
        )

        self.assertEqual(args.menu, "황금올리브")
        self.assertEqual(args.option, ["콜라 1.25L", "치즈볼"])
        self.assertEqual(args.order_type, "delivery")

    @patch("test_prepare_bbq_order.prepare_bbq_order")
    def test_main_prints_tool_result(self, mock_tool) -> None:
        import test_prepare_bbq_order

        mock_tool.func.return_value = json.dumps(
            {"ok": True, "result": "Cart ready"},
            ensure_ascii=False,
        )

        with patch("builtins.print") as mock_print:
            exit_code = test_prepare_bbq_order.main(
                ["--menu", "황금올리브", "--order-type", "pickup"]
            )

        self.assertEqual(exit_code, 0)
        mock_tool.func.assert_called_once_with("황금올리브", [], "pickup", {})
        printed = mock_print.call_args.args[0]
        self.assertIn("Cart ready", printed)


if __name__ == "__main__":
    unittest.main()

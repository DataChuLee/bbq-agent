import json
import subprocess
import unittest
from unittest.mock import patch


class PrepareBbqOrderToolTests(unittest.TestCase):
    @patch("tools.prepare_bbq_order.Path.exists", return_value=True)
    @patch("tools.prepare_bbq_order._run_browser_runner_command")
    def test_prepare_bbq_order_invokes_browser_runner_with_order_task(
        self, mock_run, _mock_exists
    ) -> None:
        from tools.prepare_bbq_order import prepare_bbq_order

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "result": "Cart is ready",
                    "current_url": "https://www.bbq.co.kr/order/cart",
                }
            ),
            stderr="",
        )

        payload = json.loads(
            prepare_bbq_order.func(
                "Golden Olive Chicken",
                ["Half chicken", "Coke 1.25L"],
                "delivery",
                {},
                menu_category="Fried",
            )
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["type"], "order_status")
        self.assertEqual(payload["status"], "cart_ready")
        self.assertEqual(
            payload["message"], "Golden Olive Chicken이 장바구니에 담겼어요."
        )
        self.assertEqual(payload["menu_name"], "Golden Olive Chicken")
        self.assertEqual(payload["expected_options"], ["Half chicken", "Coke 1.25L"])
        self.assertEqual(payload["order_type"], "delivery")
        self.assertEqual(payload["current_url"], "https://www.bbq.co.kr/order/cart")
        self.assertEqual(
            payload["next_action"],
            "BBQ 공식 사이트에서 장바구니와 결제를 확인해 주세요.",
        )

        command = mock_run.call_args.args[0]
        self.assertIn("--headed", command)
        self.assertIn("--keep-open-on-completion", command)
        self.assertIn("--manual-checkpoint", command)
        self.assertIn("--resume-task", command)
        self.assertIn("--task", command)
        task = command[command.index("--task") + 1]
        self.assertIn("Golden Olive Chicken", task)
        self.assertIn("Fried", task)
        self.assertIn("Half chicken", task)
        self.assertIn("Coke 1.25L", task)
        self.assertIn("delivery", task)
        self.assertIn("do not guess the address", task)
        self.assertIn("Do not search for, select, configure, or add any menu item", task)

        resume_task = command[command.index("--resume-task") + 1]
        self.assertIn("Continue", resume_task)
        self.assertIn("Exact selected menu name: Golden Olive Chicken", resume_task)
        self.assertIn("Menu category tab: Fried", resume_task)
        self.assertIn("Choose the exact full menu name", resume_task)
        self.assertIn("Use the custom tool named", resume_task)
        self.assertIn("Click the exact BBQ menu item by full visible name", resume_task)
        self.assertIn("Click an exact BBQ option within its option group", resume_task)
        self.assertIn(
            "Click BBQ add-to-cart only after selected options are visible",
            resume_task,
        )
        self.assertIn("Click BBQ move-to-cart only after add-to-cart", resume_task)
        self.assertIn("If an option is unavailable or ambiguous", resume_task)
        self.assertIn("Do not submit payment", resume_task)

    @patch("tools.prepare_bbq_order.Path.exists", return_value=True)
    @patch("tools.prepare_bbq_order._run_browser_runner_command")
    def test_prepare_bbq_order_parses_last_json_from_noisy_runner_stdout(
        self, mock_run, _mock_exists
    ) -> None:
        from tools.prepare_bbq_order import prepare_bbq_order

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "Press Enter after completing this step in the browser..."
                + json.dumps({"ok": True, "result": "Cart is ready"})
            ),
            stderr="",
        )

        payload = json.loads(
            prepare_bbq_order.func(
                "Golden Olive Chicken",
                ["Coke 1.25L"],
                "delivery",
                {},
                menu_category="Fried",
            )
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["type"], "order_status")
        self.assertEqual(
            payload["message"], "Golden Olive Chicken이 장바구니에 담겼어요."
        )

    @patch("tools.prepare_bbq_order.Path.exists", return_value=True)
    @patch("tools.prepare_bbq_order._run_browser_runner_command")
    def test_prepare_bbq_order_includes_option_details_in_resume_task(
        self, mock_run, _mock_exists
    ) -> None:
        from tools.prepare_bbq_order import prepare_bbq_order

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "result": "Option review needed"}),
            stderr="",
        )

        prepare_bbq_order.func(
            "Golden Olive Chicken",
            ["Coke 1.25L"],
            "delivery",
            {},
            menu_category="Fried",
            option_details=[
                {
                    "group_name": "Drink selection",
                    "option_name": "Coke 1.25L",
                    "add_price": 1500,
                    "required": True,
                }
            ],
        )

        command = mock_run.call_args.args[0]
        resume_task = command[command.index("--resume-task") + 1]
        self.assertIn("Drink selection -> Coke 1.25L", resume_task)
        self.assertIn("Coke1.25L", resume_task)
        self.assertIn("Before adding to cart, verify", resume_task)


if __name__ == "__main__":
    unittest.main()

import json
import threading
import time
import unittest


class ManualCheckpointBrokerTests(unittest.TestCase):
    def test_publish_notifies_listener_and_resume_releases_waiter(self) -> None:
        from api.services.manual_checkpoint import ManualCheckpointBroker

        broker = ManualCheckpointBroker()
        listener = broker.listen("session-1")
        checkpoint = broker.publish("session-1", "Complete login in the browser.")

        event = listener.get_nowait()
        self.assertEqual(event["event"], "manual_checkpoint")
        self.assertEqual(event["checkpoint"]["message"], "Complete login in the browser.")
        self.assertEqual(event["checkpoint"]["run_id"], checkpoint.run_id)

        resumed = []

        def waiter() -> None:
            resumed.append(checkpoint.resume_event.wait(timeout=1))

        thread = threading.Thread(target=waiter)
        thread.start()
        self.assertTrue(broker.resume("session-1", checkpoint.run_id))
        thread.join(timeout=1)

        self.assertEqual(resumed, [True])

    def test_resume_returns_false_when_checkpoint_is_not_active(self) -> None:
        from api.services.manual_checkpoint import ManualCheckpointBroker

        broker = ManualCheckpointBroker()

        self.assertFalse(broker.resume("missing-session", "missing-run"))


class PrepareBbqOrderCheckpointTests(unittest.TestCase):
    def test_runner_publishes_manual_checkpoint_and_resumes_stdin(self) -> None:
        from api.services.manual_checkpoint import ManualCheckpointBroker
        from tools import prepare_bbq_order as module

        broker = ManualCheckpointBroker()
        original_broker = module.manual_checkpoint_broker
        module.manual_checkpoint_broker = broker

        command = [
            "python",
            "runner.py",
            "--manual-checkpoint",
            "Complete login in the browser.",
        ]

        try:
            result_holder = {}

            def run_command() -> None:
                result_holder["completed"] = module._run_browser_runner_command(
                    command,
                    cwd=module.PROJECT_ROOT,
                    env={},
                    timeout=2,
                    session_id="session-1",
                    manual_checkpoint="Complete login in the browser.",
                    popen_factory=FakeCheckpointPopen,
                )

            thread = threading.Thread(target=run_command)
            thread.start()

            listener = broker.listen("session-1")
            event = listener.get(timeout=1)
            self.assertEqual(event["event"], "manual_checkpoint")
            run_id = event["checkpoint"]["run_id"]

            self.assertTrue(broker.resume("session-1", run_id))
            thread.join(timeout=1)

            completed = result_holder["completed"]
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(
                json.loads(completed.stdout),
                {"ok": True, "result": "Cart is ready"},
            )
            self.assertEqual(FakeCheckpointPopen.last_instance.stdin.writes, ["\n"])
        finally:
            module.manual_checkpoint_broker = original_broker


class FakeStream:
    def __init__(self, lines=None):
        self.lines = list(lines or [])
        self.writes = []

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        return ""

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        return None

    def close(self):
        return None


class FakeCheckpointPopen:
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.returncode = None
        self.stdin = FakeStream()
        self.stdout = FakeStream(
            [json.dumps({"ok": True, "result": "Cart is ready"})]
        )
        self.stderr = FakeStream(
            [
                "Complete login in the browser.\n",
                "Press Enter after completing this step in the browser...\n",
            ]
        )
        FakeCheckpointPopen.last_instance = self

    def wait(self, timeout=None):
        deadline = time.time() + float(timeout or 1)
        while not self.stdin.writes:
            if time.time() > deadline:
                raise TimeoutError("stdin was not resumed")
            time.sleep(0.01)
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


if __name__ == "__main__":
    unittest.main()

import unittest

from src.helper.batch import run_batch


class RunBatchTest(unittest.TestCase):
    def test_all_succeed(self):
        succeeded, failed = run_batch(["a", "b"], lambda x: None, lambda x: x, "process")
        self.assertEqual((succeeded, failed), (2, 0))

    def test_all_fail(self):
        def action(x):
            raise ValueError("boom")

        succeeded, failed = run_batch(["a", "b"], action, lambda x: x, "process")
        self.assertEqual((succeeded, failed), (0, 2))

    def test_empty_items(self):
        self.assertEqual(run_batch([], lambda x: None, lambda x: x, "process"), (0, 0))

    def test_mixed_calls_on_success_only_for_successes(self):
        def action(x):
            if x == "bad":
                raise ValueError("boom")

        successes = []
        succeeded, failed = run_batch(["a", "bad", "b"], action, lambda x: x, "process", successes.append)
        self.assertEqual((succeeded, failed), (2, 1))
        self.assertEqual(successes, ["a", "b"])

    def test_failure_does_not_stop_remaining_items(self):
        seen = []

        def action(x):
            seen.append(x)
            if x == "bad":
                raise ValueError("boom")

        run_batch(["bad", "a", "b"], action, lambda x: x, "process")
        self.assertEqual(seen, ["bad", "a", "b"])


if __name__ == "__main__":
    unittest.main()

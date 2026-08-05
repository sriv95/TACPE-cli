"""Generic batch runner: apply an action to each item, catching and reporting per-item failures."""

from rich.console import Console

console = Console()


def run_batch(items: list, action, describe, verb: str, on_success=None) -> tuple[int, int]:
    """Run action(item) for each item, catching exceptions and reporting per-item failures.
    Input: items (list), action (callable) - item -> None, may raise,
        describe (callable) - item -> str, used in the failure message,
        verb (str) - verb for the failure message (e.g. "add", "delete"),
        on_success (callable | None) - item -> None, called after each success.
    Output: (tuple[int, int]) (succeeded, failed) counts.
    """
    succeeded = failed = 0
    for item in items:
        try:
            action(item)
        except Exception as e:
            failed += 1
            console.print(f"[red]Failed to {verb} {describe(item)}: {e}[/red]")
            continue
        succeeded += 1
        if on_success:
            on_success(item)
    return succeeded, failed


def _demo() -> None:
    """Self-check: success/failure counting and the on_success callback (no network)."""

    def action(x):
        if x == "bad":
            raise ValueError("boom")

    successes = []
    succeeded, failed = run_batch(["a", "bad", "b"], action, lambda x: x, "process", successes.append)
    assert succeeded == 2
    assert failed == 1
    assert successes == ["a", "b"]


if __name__ == "__main__":
    _demo()
    print("OK")

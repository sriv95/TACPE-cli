"""Shared HTTP request helper — injects the session Cookie header globally."""

import functools
import json
import time
import urllib.error
import urllib.request

from rich.console import Console

console = Console()

_cookie: str | None = None

RETRY_WAITS = (1, 5, 10, 30)


def retry_with_backoff(waits: tuple[int, ...] = RETRY_WAITS):
    """Decorator: retry a function on urllib.error.URLError with growing backoff, forever.
    Input: waits (tuple[int, ...]) - wait seconds per attempt, last value repeats once exhausted.
    Output: decorator wrapping the target function with the same signature.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait_index = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        console.print("[yellow]Session expired — logging in again.[/yellow]")
                        from src.auth import login  # lazy: auth imports set_cookie from this module

                        login()
                        continue
                    raise
                except urllib.error.URLError as e:
                    wait = waits[min(wait_index, len(waits) - 1)]
                    console.print(f"[red]Error: {e} — retrying in {wait}s[/red]")
                    time.sleep(wait)
                    wait_index += 1

        return wrapper

    return decorator


def set_cookie(cookie: str) -> None:
    """Store the session cookie used by all future requests.
    Input: cookie (str) - raw Cookie header string.
    """
    global _cookie
    _cookie = cookie


@retry_with_backoff()
def request(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> bytes:
    """Send an HTTP request with the stored Cookie header attached. Retries on network error.
    Input: url (str), method (str), data (bytes | None), headers (dict | None).
    Output: (bytes) raw response body.
    """
    if _cookie is None:
        raise RuntimeError("No cookie set. Call set_cookie() first.")
    req = urllib.request.Request(url, data=data, headers={**(headers or {}), "Cookie": _cookie}, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        console.print(f"[red]HTTP {e.code} body: {e.read().decode(errors='replace')}[/red]")
        raise


def post_json(url: str, payload: dict) -> bytes:
    """POST a JSON payload to the API.
    Input: url (str), payload (dict).
    Output: (bytes) raw response body.
    """
    return request(url, method="POST", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})

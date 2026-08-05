"""Detached helper: open a URL in Playwright's Chromium with the saved session cookie injected.
Run via `python -m src.browser_launcher <url>`, spawned detached so the caller doesn't block.
"""

import sys

from src.auth import load_cookie
from src.const import BASE_URL


def _parse_cookie_header(cookie: str) -> list[dict]:
    """Convert a raw 'name=value; name2=value2' Cookie header into Playwright cookie dicts.
    Input: cookie (str) - raw Cookie header string.
    Output: (list[dict]) {name, value, url} per cookie.
    """
    return [
        {"name": name, "value": value, "url": BASE_URL}
        for name, _, value in (part.partition("=") for part in cookie.split("; "))
        if value
    ]


def main(url: str) -> None:
    """Launch Chromium, inject the saved cookie, navigate, and block until the tab closes.
    Input: url (str) - page to open.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        try:
            context.add_cookies(_parse_cookie_header(load_cookie()))
        except FileNotFoundError:
            pass
        page = context.new_page()
        page.goto(url)
        page.wait_for_event("close", timeout=0)
        if browser.is_connected():
            browser.close()


def _demo() -> None:
    """Self-check: cookie header parsing (no network)."""
    parsed = _parse_cookie_header("a=1; b=2")
    assert parsed == [
        {"name": "a", "value": "1", "url": BASE_URL},
        {"name": "b", "value": "2", "url": BASE_URL},
    ]
    assert _parse_cookie_header("") == []


if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        _demo()
        print("OK")

"""Cookie acquisition for the CPE TA site (Microsoft Entra ID login, no plain form)."""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import questionary
from rich.console import Console

BASE_URL = "https://ta.cpe.eng.cmu.ac.th"
TEST_URL = f"{BASE_URL}/api/user/getWithSession"
COOKIE_FILE = Path(__file__).resolve().parent.parent / ".cookie"

console = Console()


def save_cookie(cookie: str) -> None:
    COOKIE_FILE.write_text(cookie.strip() + "\n")


def load_cookie() -> str:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"No cookie saved. Run `python -m src.auth login` first ({COOKIE_FILE}).")
    return COOKIE_FILE.read_text().strip()


def login_manual() -> str:
    console.print("1. Log into [bold]https://ta.cpe.eng.cmu.ac.th[/bold] in your browser.")
    console.print("2. Open DevTools -> Network tab, reload the page.")
    console.print("3. Click any request to ta.cpe.eng.cmu.ac.th -> Headers -> copy the [bold]Cookie[/bold] value.")
    cookie = questionary.text("Paste Cookie header:").ask()
    if not cookie:
        raise RuntimeError("No cookie entered.")
    return cookie


def login_browser() -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL)
        console.print("Complete the CMU Account login (incl. MFA) in the opened browser window.")
        # only the post-login OAuth callback confirms login finished — the home page
        # URL itself would otherwise match a broader "back on this site" pattern instantly
        page.wait_for_url(f"{BASE_URL}/cmuEntraIDCallback**", timeout=0)
        # give the callback route a moment to finish setting cookies
        page.wait_for_load_state("networkidle")

        cookies = context.cookies(BASE_URL)
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        browser.close()

    if not cookie_header:
        raise RuntimeError("No cookies captured — login may not have completed.")
    return cookie_header


def test_cookie(cookie: str) -> bool:
    req = urllib.request.Request(TEST_URL, headers={"Cookie": cookie})
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            console.print(f"[bold green]OK[/bold green] {resp.status} {TEST_URL}")
            try:
                console.print_json(json.dumps(json.loads(body)))
            except json.JSONDecodeError:
                console.print(body)
            return True
    except urllib.error.HTTPError as e:
        console.print(f"[bold red]FAIL[/bold red] {e.code} {TEST_URL}")
        console.print(e.read().decode(errors="replace"))
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    login = sub.add_parser("login", help="Acquire and save the auth cookie")
    login.add_argument("--method", choices=["manual", "browser"])
    sub.add_parser("test", help="Test the saved cookie against the API")
    args = parser.parse_args()

    if args.command == "login":
        method = args.method or questionary.select(
            "How do you want to get the cookie?",
            choices=[
                questionary.Choice("Browser login (opens Chromium, handles MFA)", value="browser"),
                questionary.Choice("Manual paste (copy Cookie header from DevTools)", value="manual"),
            ],
        ).ask()
        cookie = (login_browser if method == "browser" else login_manual)()
        if test_cookie(cookie):
            save_cookie(cookie)
            console.print(f"[green]Saved[/green] to {COOKIE_FILE}")
        else:
            console.print("[red]Not saved[/red] — cookie failed the auth check.")
    elif args.command == "test":
        test_cookie(load_cookie())


if __name__ == "__main__":
    main()

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
    save_cookie(cookie)
    console.print(f"[green]Saved[/green] to {COOKIE_FILE}")
    return cookie


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
    sub.add_parser("login", help="Acquire and save the auth cookie")
    sub.add_parser("test", help="Test the saved cookie against the API")
    args = parser.parse_args()

    if args.command == "login":
        cookie = login_manual()
        test_cookie(cookie)
    elif args.command == "test":
        test_cookie(load_cookie())


if __name__ == "__main__":
    main()

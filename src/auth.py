"""Cookie acquisition for the CPE TA site (Microsoft Entra ID login, no plain form)."""

import urllib.error
import urllib.request
from pathlib import Path

import questionary
from rich.console import Console

from src.const import BASE_URL, TEST_URL
from src.exceptions import UserCancelled
from src.request import set_cookie
COOKIE_FILE = Path(__file__).resolve().parent.parent / ".cache" / ".cookie"

console = Console()


def save_cookie(cookie: str) -> None:
    """Persist the cookie to disk.
    Input: cookie (str) - raw Cookie header string.
    """
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(cookie.strip() + "\n")


def load_cookie() -> str:
    """Read the previously saved cookie.
    Output: (str) raw Cookie header string; raises if none saved.
    """
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"No cookie saved. Run `python -m src.auth login` first ({COOKIE_FILE}).")
    return COOKIE_FILE.read_text().strip()


MANUAL_INSTRUCTION = (
    "\n  1. Log into https://ta.cpe.eng.cmu.ac.th in your browser."
    "\n  2. Open DevTools -> Network tab, reload the page."
    "\n  3. Click any request to ta.cpe.eng.cmu.ac.th -> Headers -> copy the Cookie value.\n"
)


def login_manual() -> str:
    """Prompt user to paste a Cookie header copied from DevTools.
    Output: (str) raw Cookie header string.
    """
    cookie = questionary.text(
        "Paste Cookie header:",
        instruction=MANUAL_INSTRUCTION,
        erase_when_done=True,
    ).ask()
    if cookie is None:
        raise UserCancelled
    if not cookie:
        raise RuntimeError("No cookie entered.")
    return cookie


def login_browser() -> str:
    """Open a real browser for CMU Entra ID login and capture the session cookies.
    Output: (str) assembled Cookie header string.
    """
    from playwright.sync_api import Error as PlaywrightError, sync_playwright

    with console.status("Opening browser") as status:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=False)
            except PlaywrightError as e:
                if "Executable doesn't exist" not in str(e):
                    raise
                raise SystemExit(
                    "Browser not installed. Run: uvx playwright install chromium"
                ) from None
            context = browser.new_context()
            page = context.new_page()
            page.goto(BASE_URL)
            login_link = page.locator("a[href*='login.microsoftonline.com']")
            if login_link.count() > 0:
                page.goto(login_link.first.get_attribute("href"))
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
    """Check whether a cookie is still authenticated.
    Input: cookie (str) - raw Cookie header string.
    Output: (bool) True if valid.
    """
    req = urllib.request.Request(TEST_URL, headers={"Cookie": cookie})
    with console.status("Logging In") as status:
        try:
            with urllib.request.urlopen(req):
                status.update("[bold green]Login Successful[/bold green]")
                success = True
        except urllib.error.HTTPError:
            success = False

    # status spinner is transient — reprint on success so it stays visible;
    # on failure just let it vanish, the caller decides what to do next
    if success:
        console.print("[bold green]Login Successful[/bold green]")
    return success


def login_prompt() -> str:
    """Ask user to pick browser or manual login, run it, verify and save the result.
    Output: (str) validated Cookie header string.
    """
    method = questionary.select(
        "How do you want to login?",
        choices=[
            questionary.Choice("1. Browser login", value="browser"),
            questionary.Choice("2. Manual paste Cookie", value="manual"),
        ],
    ).ask()
    if method is None:
        raise UserCancelled
    cookie = (login_browser if method == "browser" else login_manual)()
    if not test_cookie(cookie):
        raise RuntimeError("Login failed the auth check after login.")
    save_cookie(cookie)
    return cookie


def login() -> str:
    """Return a working cookie: try the saved one first, else prompt login.
    Output: (str) valid Cookie header string; also sets it as the global request cookie.
    """
    try:
        cookie = load_cookie()
    except FileNotFoundError:
        cookie = None

    if cookie:
        if test_cookie(cookie):
            set_cookie(cookie)
            return cookie
        console.print("[yellow]Saved cookie invalid — logging in again.[/yellow]")

    cookie = login_prompt()
    set_cookie(cookie)
    return cookie

"""Cookie acquisition for the CPE TA site (Microsoft Entra ID login, no plain form)."""

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import questionary
from rich.console import Console

from src.func.const import BASE_URL, TEST_URL
from src.helper.prompt import ask
from src.func.request import set_cookie
COOKIE_FILE = Path(__file__).resolve().parent.parent / ".cache" / ".cookie"

console = Console()


def save_cookie(cookie: str) -> None:
    """Persist the cookie to disk.
    Input: cookie (str) - raw Cookie header string.
    """
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(cookie.strip() + "\n")


def logout() -> None:
    """Delete saved cookie file, if any."""
    COOKIE_FILE.unlink(missing_ok=True)


def load_cookie() -> str:
    """Read the previously saved cookie.
    Output: (str) raw Cookie header string; raises if none saved.
    """
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"No cookie saved. Run `python -m src.cli.auth login` first ({COOKIE_FILE}).")
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
    cookie = ask(questionary.text(
        "Paste Cookie header:",
        instruction=MANUAL_INSTRUCTION,
        erase_when_done=True,
    ))
    if not cookie:
        raise RuntimeError("No cookie entered.")
    return cookie


def login_browser() -> str:
    """Open a real browser for CMU Entra ID login and capture the session cookies.
    Output: (str) assembled Cookie header string.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        raise SystemExit(
            "playwright not installed. Run: uv tool install --force tacpe"
        ) from None

    def _run(p) -> str:
        browser = p.chromium.launch(headless=False)
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
        return cookie_header

    try:
        with console.status("Opening browser"):
            with sync_playwright() as p:
                cookie_header = _run(p)
    except PlaywrightError as e:
        if "Executable doesn't exist" not in str(e):
            raise
        # prompt/install run outside console.status — its Live spinner takes over
        # the terminal, so a Rich prompt or the installer's own progress bar
        # rendered underneath it looks frozen (or can't be answered at all)
        if not ask(questionary.confirm(
            "Chromium not installed. Install it now?", default=True,
        )):
            raise SystemExit("Run: uvx playwright install chromium") from None
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
        with console.status("Opening browser"):
            with sync_playwright() as p:
                cookie_header = _run(p)

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


def login_prompt(method: str | None = None) -> str:
    """Ask user to pick browser or manual login (unless method is given), run it, verify and save the result.
    Input: method (str | None) - "browser" or "manual" to skip the select prompt.
    Output: (str) validated Cookie header string.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
    except ImportError:
        PlaywrightError = ()  # noqa: N806 — manual login never raises it, so nothing to catch

    while True:
        chosen = method or ask(questionary.select(
            "How do you want to login?",
            choices=[
                questionary.Choice("1. Browser login", value="browser"),
                questionary.Choice("2. Manual paste Cookie", value="manual"),
            ],
        ))
        try:
            cookie = (login_browser if chosen == "browser" else login_manual)()
        except PlaywrightError as e:
            if "closed" not in str(e).lower():
                raise
            console.print("[yellow]Browser closed before login finished — try again.[/yellow]")
            continue
        if not test_cookie(cookie):
            raise RuntimeError("Login failed the auth check after login.")
        save_cookie(cookie)
        return cookie


def check_login() -> bool:
    """Check for a saved, still-valid cookie and set it as the active cookie. Never prompts.
    Output: (bool) True if logged in (cookie set), False otherwise.
    """
    try:
        cookie = load_cookie()
    except FileNotFoundError:
        return False
    if not test_cookie(cookie):
        return False
    set_cookie(cookie)
    return True


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

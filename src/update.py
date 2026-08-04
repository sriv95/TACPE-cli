"""Check for a newer published version and offer to self-update."""

import subprocess
import sys
import tomllib
import urllib.request
from importlib.metadata import version

import questionary
from rich.console import Console

REPO_URL = "https://github.com/sriv95/TACPE-csv-to-works"
PYPROJECT_RAW_URL = "https://raw.githubusercontent.com/sriv95/TACPE-csv-to-works/main/pyproject.toml"

console = Console()


def _latest_version() -> str | None:
    """Fetch the version published on the main branch.
    Output: (str | None) version string, or None if it couldn't be checked.
    """
    try:
        with urllib.request.urlopen(PYPROJECT_RAW_URL, timeout=3) as resp:
            data = tomllib.loads(resp.read().decode())
        return data["project"]["version"]
    except Exception:
        return None


def _installed_via() -> str:
    """Guess which tool manages this install by inspecting the venv path.
    Output: (str) "pipx" or "uv".
    """
    return "pipx" if "pipx" in sys.prefix else "uv"


def check_update() -> None:
    """Prompt to update if a newer version is published; runs the update and exits if accepted."""
    latest = _latest_version()
    current = version("tacpe-csv-to-works")
    if not latest or latest == current:
        return

    if not questionary.confirm(
        f"Update available: {current} -> {latest}. Update now?", default=True
    ).ask():
        return

    manager = _installed_via()
    cmd = [manager] + (["tool", "upgrade"] if manager == "uv" else ["upgrade"]) + ["tacpe-csv-to-works"]

    if sys.platform == "win32":
        # Windows locks the running exe — it can't be overwritten by this same process.
        console.print(
            "[yellow]Close tacpe, then run this to update:[/yellow]\n  " + " ".join(cmd)
        )
        raise SystemExit(0)

    console.print(f"Updating via {manager}...")
    subprocess.run(cmd, check=True)
    console.print("[green]Updated. Restart tacpe to use the new version.[/green]")
    raise SystemExit(0)

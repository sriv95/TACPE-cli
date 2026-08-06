"""Non-interactive CLI subcommands (e.g. `tacpe login browser`), separate from the default interactive flow."""

import argparse

from rich.console import Console

from src.cli.auth import login, login_prompt, logout
from src.cli.course import current_reg_time, list_courses

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tacpe")
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login", help="Log in and save the session cookie")
    login_parser.add_argument("method", nargs="?", choices=["browser", "cookie"], default=None)

    subparsers.add_parser("logout", help="Remove the saved session cookie")

    list_parser = subparsers.add_parser("list", help="List courses or works")
    list_subparsers = list_parser.add_subparsers(dest="list_command")
    courses_parser = list_subparsers.add_parser("courses", help="List courses you TA for")
    courses_parser.add_argument("--term", "--t", dest="term", type=int, default=None)
    courses_parser.add_argument("--year", "--y", dest="year", default=None)

    return parser


def _resolve_term_year(term: int | None, year: str | None) -> tuple[int, int]:
    """Resolve --term/--year into a concrete (year, term), fetching the current one where needed.
    Input: term (int | None), year (str | None) - year as plain "YYYY" or combined "term/YYYY".
    Output: (tuple[int, int]) (year, term).
    """
    if year is None:
        if term is None:
            return current_reg_time()
        return current_reg_time()[0], term

    if "/" in year:
        term_part, year_part = year.split("/", 1)
        combo_term, combo_year = int(term_part), int(year_part)
        if term is not None and term != combo_term:
            raise SystemExit(f"--term {term} does not match term {combo_term} in --year {year}")
        return combo_year, combo_term

    resolved_term = term if term is not None else current_reg_time()[1]
    return int(year), resolved_term


def _list_courses_command(term: int | None, year: str | None) -> None:
    """Print courseNo/section/courseName for every course the user TAs, for a resolved term/year."""
    reg_year, reg_term = _resolve_term_year(term, year)
    login()
    for ta in list_courses(reg_year, reg_term):
        template = ta["course"]["courseTemplate"]
        console.print(f"{template['courseNo']} | Sec:{ta['course']['section']:03d} | {template['courseName']}")


def run(argv: list[str] | None = None) -> bool:
    """Parse argv for a standalone subcommand and run it.
    Output: (bool) True if a subcommand was handled (caller should not continue to the interactive flow).
    """
    args = build_parser().parse_args(argv)
    if args.command == "login":
        method = "manual" if args.method == "cookie" else args.method
        login_prompt(method)
        return True
    if args.command == "logout":
        logout()
        console.print("[bold green]Logged out[/bold green]")
        return True
    if args.command == "list":
        if args.list_command == "courses":
            _list_courses_command(args.term, args.year)
        else:
            console.print("Available list commands: courses")
        return True
    return False

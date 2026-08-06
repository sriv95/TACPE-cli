"""Non-interactive CLI subcommands (e.g. `tacpe login browser`), separate from the default interactive flow."""

import argparse

from rich.console import Console

from src.cli.auth import check_login, login_prompt, logout
from src.cli.course import current_reg_time, list_courses
from src.cli.work.works import fetch_works, format_date, format_time

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tacpe")
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login", help="Log in and save the session cookie")
    login_parser.add_argument("method", nargs="?", choices=["browser", "cookie"], default=None)

    subparsers.add_parser("logout", help="Remove the saved session cookie")

    list_parser = subparsers.add_parser("list", help="List courses, or works for a course")
    list_parser.add_argument("target", nargs="?", default=None, help="'courses', or a courseNo/courseId")
    list_parser.add_argument("--term", "--t", dest="term", type=int, default=None)
    list_parser.add_argument("--year", "--y", dest="year", default=None)
    list_parser.add_argument("--sec", "--section", dest="section", type=int, default=None)

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


def _print_course_line(ta: dict) -> None:
    template = ta["course"]["courseTemplate"]
    console.print(f"{template['courseNo']} | Sec:{ta['course']['section']:03d} | {template['courseName']}")


def _list_courses_command(term: int | None, year: str | None) -> None:
    """Print courseNo/section/courseName for every course the user TAs, for a resolved term/year."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    for ta in list_courses(reg_year, reg_term):
        _print_course_line(ta)


def _resolve_course(courses: list[dict], identifier: str, section: int | None) -> dict:
    """Find a TA course entry by courseId, or by courseNo (+ optional section, else first match).
    Input: courses (list[dict]) - TA/course dicts, identifier (str) - courseId or courseNo,
        section (int | None) - narrows a courseNo match.
    Output: (dict) matching TA/course entry; exits with an error if none found.
    """
    try:
        course_id = int(identifier)
    except ValueError:
        course_id = None
    if course_id is not None:
        match = next((ta for ta in courses if ta["courseId"] == course_id), None)
        if match:
            return match

    matches = [ta for ta in courses if ta["course"]["courseTemplate"]["courseNo"] == identifier]
    if section is not None:
        matches = [ta for ta in matches if ta["course"]["section"] == section]
    if not matches:
        raise SystemExit(f"No course found matching {identifier}" + (f" section {section}" if section is not None else ""))
    return matches[0]


def _list_works_command(identifier: str, term: int | None, year: str | None, section: int | None) -> None:
    """Print the works list for a course, resolved by courseNo or courseId."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), identifier, section)
    _print_course_line(course)
    for w in fetch_works(course["courseId"]):
        console.print(f"{format_date(w['date'])} | {format_time(w['time'])} | {w['work']}")


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
        if args.target is None:
            console.print("Available: list courses | list <courseNo|courseId>")
        elif args.target == "courses":
            _list_courses_command(args.term, args.year)
        else:
            _list_works_command(args.target, args.term, args.year, args.section)
        return True
    return False

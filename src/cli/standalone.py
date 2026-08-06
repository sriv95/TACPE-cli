"""Non-interactive CLI subcommands (e.g. `tacpe login browser`), separate from the default interactive flow."""

import argparse
import json
from importlib.metadata import version

from rich.console import Console

from src.cli.auth import check_login, login_prompt, logout
from src.cli.course import current_reg_time, list_courses
from src.cli.work.auto_slot import (
    _fmt,
    _filter_by_min_start,
    _validate_bulk_row,
    _validate_duration,
    default_pick,
    entry_overlap_reasons,
    fetch_all_course_works,
    find_free_slots,
    find_overlap_conflicts,
    print_overlap_conflicts,
    slots_with_overlap,
)
from src.cli.work.bulk_works import REQUIRED_COLUMNS, _validate_row, read_csv_rows
from src.cli.work.timetable import WEEKDAYS, _row_label, load_timetable, save_timetable
from src.cli.work.works import (
    delete_work,
    edit_work,
    fetch_works,
    format_date,
    format_entry_line,
    format_time,
    minutes,
    parse_time,
    split_time,
    submit_work,
    validate_date,
    validate_work,
)
from src.helper.batch import run_batch

console = Console()


TERM_HELP = "Academic term, e.g. 1 (default: current term)"
YEAR_HELP = 'Academic year, e.g. 2026, or "term/year" e.g. 1/2026 (default: current year)'
SECTION_HELP = "Course section number, to disambiguate a courseNo with multiple sections (default: first match)"
JSON_HELP = "Output as JSON instead of formatted text"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tacpe", description="CLI to add work entries into the CPE TA site, one at a time or in bulk from a CSV."
    )
    parser.add_argument("--version", action="version", version=f"tacpe {version('tacpe')}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("help", help="Show this help message")
    subparsers.add_parser("version", help="Show the installed version")

    login_parser = subparsers.add_parser("login", help="Log in and save the session cookie")
    login_parser.add_argument(
        "method", nargs="?", choices=["browser", "cookie"], default=None,
        help="'browser' to log in via a real browser, 'cookie' to paste a Cookie header manually (default: prompt to choose)",
    )

    subparsers.add_parser("logout", help="Remove the saved session cookie")

    courses_parser = subparsers.add_parser("courses", help="List courses you TA for")
    courses_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    courses_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    courses_parser.add_argument("--json", dest="as_json", action="store_true", help=JSON_HELP)

    timetable_parser = subparsers.add_parser("timetable", help="Show or edit the saved enrolled-course timetable")
    timetable_parser.add_argument(
        "action", nargs="?", choices=["list", "add", "edit", "delete"], default="list", help="Defaults to 'list'"
    )
    timetable_parser.add_argument("--name", dest="name", default=None, help="Course/entry name (required for add/edit)")
    timetable_parser.add_argument(
        "--day", dest="day", choices=WEEKDAYS, default=None, help="Weekday (required for add/edit)"
    )
    timetable_parser.add_argument(
        "--startTime", "--st", dest="start_time", default=None,
        help="Start time: HH:MM, HHMM, H, or H.mm, any minute (required for add/edit)",
    )
    timetable_parser.add_argument(
        "--endTime", "--et", dest="end_time", default=None,
        help="End time, same format as --startTime, after --startTime (required for add/edit)",
    )
    timetable_parser.add_argument(
        "--index", dest="index", type=int, default=None,
        help="0-based entry index, see `tacpe timetable list --json` (required for edit/delete)",
    )
    timetable_parser.add_argument("--json", dest="as_json", action="store_true", help=JSON_HELP)

    check_parser = subparsers.add_parser("check", help="Check for overlapping work entries across all courses in a term")
    check_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    check_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    check_parser.add_argument("--json", dest="as_json", action="store_true", help=JSON_HELP)

    list_parser = subparsers.add_parser("list", help="List work entries for a course")
    list_parser.add_argument("target", nargs="?", default=None, help="courseNo or courseId (see `tacpe courses`)")
    list_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    list_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    list_parser.add_argument("--sec", "--section", dest="section", type=int, default=None, help=SECTION_HELP)
    list_parser.add_argument("--json", dest="as_json", action="store_true", help=JSON_HELP)

    add_parser = subparsers.add_parser(
        "add",
        help="Add a work entry to a course (single, or bulk from a CSV; checks for issues, no confirmation prompt)",
    )
    add_parser.add_argument("target", help="courseNo or courseId (see `tacpe courses`)")
    add_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    add_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    add_parser.add_argument("--sec", "--section", dest="section", type=int, default=None, help=SECTION_HELP)
    add_parser.add_argument("--date", dest="date", default=None, help="Work date, YYYY-MM-DD (required unless --bulk)")
    add_parser.add_argument(
        "--startTime", "--st", dest="start_time", default=None,
        help="Start time: HH:MM, HHMM, H, or H.mm, minutes must be 00/30 (required unless --bulk)",
    )
    add_parser.add_argument(
        "--endTime", "--et", dest="end_time", default=None,
        help="End time, same format as --startTime, at least 1hr after it (required unless --bulk)",
    )
    add_parser.add_argument(
        "--work", "--task", dest="work", default=None, help="Task description (required unless --bulk)"
    )
    add_parser.add_argument(
        "--bulk", dest="bulk", default=None,
        help="CSV file path with columns date,startTime,endTime,work — instead of --date/--startTime/--endTime/--work",
    )
    add_parser.add_argument(
        "--force", "--no-check", dest="no_check", action="store_true",
        help="Skip the validation/overlap check",
    )

    edit_parser = subparsers.add_parser(
        "edit", help="Edit an existing work entry by workId (see `tacpe list --json`), no confirmation prompt"
    )
    edit_parser.add_argument("target", help="courseNo or courseId (see `tacpe courses`)")
    edit_parser.add_argument("--workId", dest="work_id", required=True, help="Work entry ID to edit")
    edit_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    edit_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    edit_parser.add_argument("--sec", "--section", dest="section", type=int, default=None, help=SECTION_HELP)
    edit_parser.add_argument("--date", dest="date", required=True, help="New work date, YYYY-MM-DD")
    edit_parser.add_argument(
        "--startTime", "--st", dest="start_time", required=True,
        help="New start time: HH:MM, HHMM, H, or H.mm, minutes must be 00/30",
    )
    edit_parser.add_argument(
        "--endTime", "--et", dest="end_time", required=True,
        help="New end time, same format as --startTime, at least 1hr after it",
    )
    edit_parser.add_argument("--work", "--task", dest="work", required=True, help="New task description")
    edit_parser.add_argument(
        "--force", "--no-check", dest="no_check", action="store_true",
        help="Skip the validation/overlap check",
    )

    auto_parser = subparsers.add_parser(
        "auto",
        help="Auto-find a free slot and add a work entry (single, or bulk from a CSV), no confirmation prompt",
    )
    auto_parser.add_argument("target", help="courseNo or courseId (see `tacpe courses`)")
    auto_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    auto_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    auto_parser.add_argument("--sec", "--section", dest="section", type=int, default=None, help=SECTION_HELP)
    auto_parser.add_argument("--date", dest="date", default=None, help="Work date, YYYY-MM-DD (required unless --bulk)")
    auto_parser.add_argument(
        "--workHour", "--wh", dest="work_hour", default=None,
        help="Duration in hours, multiple of 0.5, e.g. 2 or 2.5 (required unless --bulk)",
    )
    auto_parser.add_argument(
        "--work", "--task", dest="work", default=None, help="Task description (required unless --bulk)"
    )
    auto_parser.add_argument(
        "--startTime", "--st", dest="start_time", default=None,
        help="Minimum start time: HH:MM, HHMM, H, or H.mm (optional, ignored with --bulk)",
    )
    auto_parser.add_argument(
        "--bulk", dest="bulk", default=None,
        help="CSV file path with columns date,workHour,work,startTime(optional) — instead of --date/--workHour/--work/--startTime",
    )
    auto_parser.add_argument(
        "--force", "--no-check", dest="no_check", action="store_true",
        help="Skip the timetable/existing-works conflict check (places the slot at the default position, ignoring conflicts)",
    )

    delete_parser = subparsers.add_parser(
        "delete", help="Delete an existing work entry by workId (see `tacpe list --json`), no confirmation prompt"
    )
    delete_parser.add_argument("target", help="courseNo or courseId (see `tacpe courses`)")
    delete_parser.add_argument("--workId", dest="work_id", required=True, help="Work entry ID to delete")
    delete_parser.add_argument("--term", "--t", dest="term", type=int, default=None, help=TERM_HELP)
    delete_parser.add_argument("--year", "--y", dest="year", default=None, help=YEAR_HELP)
    delete_parser.add_argument("--sec", "--section", dest="section", type=int, default=None, help=SECTION_HELP)

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


def _print_json(data) -> None:
    """Print data as indented JSON, bypassing Rich markup parsing.
    Input: data - JSON-serializable.
    """
    print(json.dumps(data, indent=2))


def _print_course_line(ta: dict) -> None:
    template = ta["course"]["courseTemplate"]
    console.print(f"{template['courseNo']} | Sec:{ta['course']['section']:03d} | {template['courseName']}")


def _course_row(ta: dict) -> dict:
    template = ta["course"]["courseTemplate"]
    return {"courseId": ta["courseId"], "courseNo": template["courseNo"], "section": ta["course"]["section"], "courseName": template["courseName"]}


def _list_courses_command(term: int | None, year: str | None, as_json: bool) -> None:
    """Print courseNo/section/courseName for every course the user TAs, for a resolved term/year."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    courses = list_courses(reg_year, reg_term)
    if as_json:
        _print_json([_course_row(ta) for ta in courses])
        return
    for ta in courses:
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


def _work_row(w: dict) -> dict:
    start, end = split_time(w["time"])
    return {
        "workId": w["_id"], "date": format_date(w["date"]), "startTime": start, "endTime": end,
        "hours": (minutes(end) - minutes(start)) / 60, "work": w["work"],
    }


def _list_works_command(identifier: str, term: int | None, year: str | None, section: int | None, as_json: bool) -> None:
    """Print the works list for a course, resolved by courseNo or courseId; each row includes workId
    (for use with the future 'edit'/'delete' commands)."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), identifier, section)
    works = fetch_works(course["courseId"])
    if as_json:
        _print_json(_course_row(course) | {"works": [_work_row(w) for w in works]})
        return
    _print_course_line(course)
    for w in works:
        console.print(f"{w['_id']} | {format_date(w['date'])} | {format_time(w['time'])} | {w['work']}")


def _resolve_work(course_id: int, work_id: str) -> dict:
    """Find a work entry by workId within a course.
    Input: course_id (int), work_id (str).
    Output: (dict) matching work entry; exits with an error if none found.
    """
    match = next((w for w in fetch_works(course_id) if w["_id"] == work_id), None)
    if match is None:
        raise SystemExit(f"--workId: no work entry {work_id!r} found for this course")
    return match


def _timetable_list_command(as_json: bool) -> None:
    """Print saved timetable entries, no login required."""
    entries = load_timetable()
    if as_json:
        _print_json([{"index": i} | e for i, e in enumerate(entries)])
        return
    if not entries:
        console.print("No timetable entries yet.")
        return
    for i, entry in enumerate(entries):
        console.print(f"{i} | {_row_label(entry)}")


def _validate_timetable_entry(name: str | None, day: str | None, start_time: str | None, end_time: str | None) -> dict:
    """Validate add/edit timetable fields and build an entry dict, exiting on any error."""
    missing = [n for n, v in {"--name": name, "--day": day, "--startTime/--st": start_time, "--endTime/--et": end_time}.items() if v is None]
    if missing:
        raise SystemExit(f"Missing required: {', '.join(missing)}")
    start = parse_time(start_time, strict=False)
    if start is None:
        raise SystemExit("--startTime: invalid format")
    end = parse_time(end_time, strict=False)
    if end is None:
        raise SystemExit("--endTime: invalid format")
    if minutes(end) <= minutes(start):
        raise SystemExit("--endTime must be after --startTime")
    return {"name": name, "weekday": WEEKDAYS.index(day), "start": start, "end": end}


def _resolve_timetable_index(entries: list[dict], index: int | None) -> int:
    if index is None:
        raise SystemExit("Missing required: --index")
    if not (0 <= index < len(entries)):
        raise SystemExit(f"--index: no timetable entry {index} (see `tacpe timetable list`)")
    return index


def _timetable_add_command(name: str | None, day: str | None, start_time: str | None, end_time: str | None) -> None:
    entry = _validate_timetable_entry(name, day, start_time, end_time)
    entries = load_timetable()
    entries.append(entry)
    save_timetable(entries)
    console.print(f"[bold green]Added:[/bold green] {_row_label(entry)}")


def _timetable_edit_command(index: int | None, name: str | None, day: str | None, start_time: str | None, end_time: str | None) -> None:
    entries = load_timetable()
    i = _resolve_timetable_index(entries, index)
    entry = _validate_timetable_entry(name, day, start_time, end_time)
    entries[i] = entry
    save_timetable(entries)
    console.print(f"[bold green]Updated:[/bold green] {_row_label(entry)}")


def _timetable_delete_command(index: int | None) -> None:
    entries = load_timetable()
    i = _resolve_timetable_index(entries, index)
    removed = entries.pop(i)
    save_timetable(entries)
    console.print(f"[bold red]Deleted:[/bold red] {_row_label(removed)}")


def _check_command(term: int | None, year: str | None, as_json: bool) -> None:
    """Report overlapping work entries across every course in a term, no timetable prompt."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    courses = list_courses(reg_year, reg_term)
    conflicts = find_overlap_conflicts(courses, load_timetable())
    if as_json:
        _print_json({"conflicts": conflicts})
        return
    print_overlap_conflicts(conflicts)


def _entry_issues(entry: dict, timetable: list[dict], all_works: list[dict], batch: list[dict]) -> list[str]:
    """Collect soft-check issues for one entry: hour bounds, and overlap vs timetable/other works/batch.
    Input: entry (dict) - date/time_start/time_end/work/hours, timetable (list[dict]),
        all_works (list[dict]) - existing work entries across courses, batch (list[dict]) - the other
        entries in the same submission, to also check against.
    Output: (list[str]) issue descriptions, [] if none.
    """
    issues = []
    if entry["hours"] % 1 != 0:
        issues.append(f"{entry['hours']:g} hrs is not a whole number of hours")
    if entry["hours"] > 4:
        issues.append(f"{entry['hours']:g} hrs exceeds max 4 hours")

    extra_busy = [
        (minutes(o["time_start"]), minutes(o["time_end"]), f"another row in this batch: {o['work']}")
        for o in batch
        if o is not entry and o["date"] == entry["date"]
    ]
    reasons = entry_overlap_reasons(
        entry["date"], entry["time_start"], entry["time_end"], timetable, all_works, extra_busy
    )
    issues.extend(f"overlaps {r}" for r in reasons)

    return issues


def _check_entries_or_abort(
    entries: list[dict], reg_year: int, reg_term: int, exclude_work_id: str | None = None
) -> None:
    """Print soft-check issues for entries (hour bounds, overlaps) and abort if any are found.
    Input: entries (list[dict]) - date/time_start/time_end/work/hours, reg_year/reg_term (int),
        exclude_work_id (str | None) - a workId to exclude from the overlap check (the entry being edited).
    """
    timetable = load_timetable()
    all_works = fetch_all_course_works(reg_year, reg_term)
    if exclude_work_id is not None:
        all_works = [w for w in all_works if w["_id"] != exclude_work_id]

    lines = [
        f"{entry['date']} {entry['time_start']}-{entry['time_end']} {entry['work']}: {issue}"
        for entry in entries
        for issue in _entry_issues(entry, timetable, all_works, entries)
    ]
    if not lines:
        return

    for line in lines:
        console.print(f"[yellow]Warning: {line}[/yellow]")
    raise SystemExit(f"{len(lines)} check(s) failed. Use --force/--no-check to skip checking.")


def _add_single(
    course_id: int, date: str, start_time: str, end_time: str, work: str,
    reg_year: int, reg_term: int, no_check: bool,
) -> None:
    """Validate, check (unless --no-check), and submit one work entry, no confirm prompt."""
    if validate_date(date) is not True:
        raise SystemExit(f"--date: {validate_date(date)}")
    start = parse_time(start_time)
    if start is None:
        raise SystemExit("--startTime: invalid format")
    end = parse_time(end_time)
    if end is None:
        raise SystemExit("--endTime: invalid format")
    if minutes(end) - minutes(start) < 60:
        raise SystemExit("--endTime must be at least 1 hour after --startTime")
    if validate_work(work) is not True:
        raise SystemExit(f"--work: {validate_work(work)}")

    entry = {"date": date, "work": work, "time_start": start, "time_end": end, "hours": (minutes(end) - minutes(start)) / 60}
    if not no_check:
        _check_entries_or_abort([entry], reg_year, reg_term)

    submit_work(course_id, entry)
    console.print(f"[bold green]Added:[/bold green] {format_entry_line(entry)}")


def _add_bulk(course_id: int, path: str, reg_year: int, reg_term: int, no_check: bool) -> None:
    """Validate, check (unless --no-check), and submit every valid row of a CSV, no confirm prompt."""
    try:
        rows = read_csv_rows(path, REQUIRED_COLUMNS)
    except FileNotFoundError:
        raise SystemExit(f"--bulk: file not found: {path}")
    if not rows:
        raise SystemExit("--bulk: no rows to submit (missing columns or empty file)")

    entries = [entry for i, row in enumerate(rows, start=2) if (entry := _validate_row(row, i))]
    if not entries:
        raise SystemExit("--bulk: no valid rows to submit")

    if not no_check:
        _check_entries_or_abort(entries, reg_year, reg_term)

    added, failed = run_batch(
        entries,
        lambda e: submit_work(course_id, e),
        lambda e: e["date"],
        "add",
        lambda e: console.print(f"[bold green]Added:[/bold green] {format_entry_line(e, with_hours=False)}"),
    )
    console.print(f"[bold green]Added {added} work(s).[/bold green]" + (f" [red]{failed} failed.[/red]" if failed else ""))


def _add_command(
    target: str, term: int | None, year: str | None, section: int | None,
    date: str | None, start_time: str | None, end_time: str | None, work: str | None, bulk: str | None,
    no_check: bool,
) -> None:
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), target, section)
    course_id = course["courseId"]
    _print_course_line(course)

    single_args = {"--date": date, "--startTime/--st": start_time, "--endTime/--et": end_time, "--work/--task": work}
    if bulk:
        given = [name for name, val in single_args.items() if val is not None]
        if given:
            raise SystemExit(f"--bulk cannot be combined with {', '.join(given)}")
        _add_bulk(course_id, bulk, reg_year, reg_term, no_check)
        return

    missing = [name for name, val in single_args.items() if val is None]
    if missing:
        raise SystemExit(f"Missing required: {', '.join(missing)} (or use --bulk)")
    _add_single(course_id, date, start_time, end_time, work, reg_year, reg_term, no_check)


def _edit_command(
    target: str, work_id: str, term: int | None, year: str | None, section: int | None,
    date: str, start_time: str, end_time: str, work: str, no_check: bool,
) -> None:
    """Validate, check (unless --no-check), and submit a full replacement for one work entry, no confirm prompt."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), target, section)
    course_id = course["courseId"]
    _print_course_line(course)
    _resolve_work(course_id, work_id)

    if validate_date(date) is not True:
        raise SystemExit(f"--date: {validate_date(date)}")
    start = parse_time(start_time)
    if start is None:
        raise SystemExit("--startTime: invalid format")
    end = parse_time(end_time)
    if end is None:
        raise SystemExit("--endTime: invalid format")
    if minutes(end) - minutes(start) < 60:
        raise SystemExit("--endTime must be at least 1 hour after --startTime")
    if validate_work(work) is not True:
        raise SystemExit(f"--work: {validate_work(work)}")

    entry = {"date": date, "work": work, "time_start": start, "time_end": end, "hours": (minutes(end) - minutes(start)) / 60}
    if not no_check:
        _check_entries_or_abort([entry], reg_year, reg_term, exclude_work_id=work_id)

    edit_work(course_id, work_id, entry)
    console.print(f"[bold green]Updated:[/bold green] {format_entry_line(entry)}")


def _delete_command(target: str, work_id: str, term: int | None, year: str | None, section: int | None) -> None:
    """Delete one work entry by workId, no confirmation prompt."""
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), target, section)
    course_id = course["courseId"]
    _print_course_line(course)
    work = _resolve_work(course_id, work_id)

    delete_work(course_id, work_id)
    console.print(f"[bold red]Deleted:[/bold red] {format_date(work['date'])} | {format_time(work['time'])} | {work['work']}")


def _auto_single(
    course_id: int, date: str, duration: float, work: str, min_start: str | None,
    reg_year: int, reg_term: int, no_check: bool,
) -> None:
    """Find a free slot for a duration on a date and submit it, no confirm prompt."""
    timetable, all_works = ([], []) if no_check else (load_timetable(), fetch_all_course_works(reg_year, reg_term))

    all_slots = slots_with_overlap(date, duration, timetable, all_works)
    if not all_slots:
        raise SystemExit(f"No {duration:g}-hour slot fits in the day.")
    if min_start:
        all_slots = _filter_by_min_start(all_slots, min_start, key=lambda s: s[0], desc="slot")

    free_times = [t for t, reasons in all_slots if not reasons]
    if not free_times:
        raise SystemExit(
            f"No free {duration:g}-hour slot on {date}. Use --force/--no-check to place one anyway (ignoring conflicts)."
        )

    time_start = default_pick(free_times)
    time_end = _fmt(minutes(time_start) + round(duration * 60))
    entry = {"date": date, "work": work, "time_start": time_start, "time_end": time_end, "hours": duration}

    submit_work(course_id, entry)
    console.print(f"[bold green]Added:[/bold green] {format_entry_line(entry)}")


def _auto_bulk(course_id: int, path: str, reg_year: int, reg_term: int, no_check: bool) -> None:
    """Find a free slot for each valid CSV row and submit all, no confirm prompt."""
    try:
        rows = read_csv_rows(path, ("date", "workHour", "work"))
    except FileNotFoundError:
        raise SystemExit(f"--bulk: file not found: {path}")
    if not rows:
        raise SystemExit("--bulk: no rows to submit (missing columns or empty file)")

    timetable, all_works = ([], []) if no_check else (load_timetable(), fetch_all_course_works(reg_year, reg_term))

    extra_busy: dict[str, list[tuple[int, int, str]]] = {}
    entries = []
    for i, row in enumerate(rows, start=2):
        parsed = _validate_bulk_row(row, i)
        if parsed is None:
            continue

        candidates = find_free_slots(
            parsed["date"], parsed["duration"], timetable, all_works, extra_busy.get(parsed["date"], [])
        )
        candidates = _filter_by_min_start(candidates, parsed["min_start"])
        if not candidates:
            console.print(f"[red]Row {i}: no free {parsed['duration']:g}-hour slot on {parsed['date']}.[/red]")
            continue

        time_start = default_pick(candidates)
        time_end = _fmt(minutes(time_start) + round(parsed["duration"] * 60))
        extra_busy.setdefault(parsed["date"], []).append(
            (minutes(time_start), minutes(time_end), "another row in this run")
        )
        entries.append(
            {"date": parsed["date"], "work": parsed["work"], "time_start": time_start, "time_end": time_end, "hours": parsed["duration"]}
        )

    if not entries:
        raise SystemExit("--bulk: no valid rows to submit (or no free slots found)")

    added, failed = run_batch(
        entries,
        lambda e: submit_work(course_id, e),
        lambda e: e["date"],
        "add",
        lambda e: console.print(f"[bold green]Added:[/bold green] {format_entry_line(e)}"),
    )
    console.print(f"[bold green]Added {added} work(s).[/bold green]" + (f" [red]{failed} failed.[/red]" if failed else ""))


def _auto_command(
    target: str, term: int | None, year: str | None, section: int | None,
    date: str | None, work_hour: str | None, work: str | None, start_time: str | None, bulk: str | None,
    no_check: bool,
) -> None:
    if not check_login():
        raise SystemExit("Not logged in. Run `tacpe login` first.")
    reg_year, reg_term = _resolve_term_year(term, year)
    course = _resolve_course(list_courses(reg_year, reg_term), target, section)
    course_id = course["courseId"]
    _print_course_line(course)

    single_args = {"--date": date, "--workHour/--wh": work_hour, "--work/--task": work}
    if bulk:
        given = [name for name, val in single_args.items() if val is not None]
        if start_time is not None:
            given.append("--startTime/--st")
        if given:
            raise SystemExit(f"--bulk cannot be combined with {', '.join(given)}")
        _auto_bulk(course_id, bulk, reg_year, reg_term, no_check)
        return

    missing = [name for name, val in single_args.items() if val is None]
    if missing:
        raise SystemExit(f"Missing required: {', '.join(missing)} (or use --bulk)")

    if validate_date(date) is not True:
        raise SystemExit(f"--date: {validate_date(date)}")
    duration_ok = _validate_duration(work_hour)
    if duration_ok is not True:
        raise SystemExit(f"--workHour: {duration_ok}")
    if validate_work(work) is not True:
        raise SystemExit(f"--work: {validate_work(work)}")

    min_start = None
    if start_time is not None:
        min_start = parse_time(start_time)
        if min_start is None:
            raise SystemExit("--startTime: invalid format")

    _auto_single(course_id, date, float(work_hour), work, min_start, reg_year, reg_term, no_check)


def run(argv: list[str] | None = None) -> bool:
    """Parse argv for a standalone subcommand and run it.
    Output: (bool) True if a subcommand was handled (caller should not continue to the interactive flow).
    """
    args = build_parser().parse_args(argv)
    if args.command == "help":
        build_parser().print_help()
        return True
    if args.command == "version":
        console.print(f"tacpe {version('tacpe')}")
        return True
    if args.command == "login":
        method = "manual" if args.method == "cookie" else args.method
        login_prompt(method)
        return True
    if args.command == "logout":
        logout()
        console.print("[bold green]Logged out[/bold green]")
        return True
    if args.command == "courses":
        _list_courses_command(args.term, args.year, args.as_json)
        return True
    if args.command == "timetable":
        if args.action == "list":
            _timetable_list_command(args.as_json)
        elif args.action == "add":
            _timetable_add_command(args.name, args.day, args.start_time, args.end_time)
        elif args.action == "edit":
            _timetable_edit_command(args.index, args.name, args.day, args.start_time, args.end_time)
        elif args.action == "delete":
            _timetable_delete_command(args.index)
        return True
    if args.command == "check":
        _check_command(args.term, args.year, args.as_json)
        return True
    if args.command == "list":
        if args.target is None:
            console.print("Usage: tacpe list <courseNo|courseId>")
        else:
            _list_works_command(args.target, args.term, args.year, args.section, args.as_json)
        return True
    if args.command == "add":
        _add_command(
            args.target, args.term, args.year, args.section,
            args.date, args.start_time, args.end_time, args.work, args.bulk,
            args.no_check,
        )
        return True
    if args.command == "edit":
        _edit_command(
            args.target, args.work_id, args.term, args.year, args.section,
            args.date, args.start_time, args.end_time, args.work, args.no_check,
        )
        return True
    if args.command == "delete":
        _delete_command(args.target, args.work_id, args.term, args.year, args.section)
        return True
    if args.command == "auto":
        _auto_command(
            args.target, args.term, args.year, args.section,
            args.date, args.work_hour, args.work, args.start_time, args.bulk,
            args.no_check,
        )
        return True
    return False

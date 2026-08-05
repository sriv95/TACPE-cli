"""Bulk-import work entries from a CSV file, submitted one at a time with retry."""

import csv

import questionary
from rich.console import Console

from src.helper.exceptions import UserCancelled
from src.helper.file import browse_file
from src.helper.prompt import ask, confirm_or_cancel
from src.cli.work.works import minutes, overlaps_lunch, parse_time, submit_work, validate_date, validate_work

console = Console()

REQUIRED_COLUMNS = ("date", "startTime", "endTime", "work")

CSV_INSTRUCTION = (
    "\n  Required columns: date, startTime, endTime, work (other columns are ignored)"
    "\n  date: YYYY-MM-DD"
    "\n  startTime/endTime: HH:MM, HHMM, H, or H.mm (minutes must be 00 or 30)"
    "\n  Example:"
    "\n    date,startTime,endTime,work"
    "\n    2026-07-04,10:00,14:00,Grading Assignment 1\n"
)


def select_csv_path(title: str = "Add bulk works - CSV file:", instruction: str = CSV_INSTRUCTION) -> str | None:
    """Ask how to locate the CSV (browse/type path/back).
    Input: title (str), instruction (str) - prompt text overrides for other CSV flows.
    Output: (str | None) file path, or None if back.
    """
    method = ask(questionary.select(
        title,
        choices=[
            questionary.Choice("1. From file... (browse)", value="browse"),
            questionary.Choice("2. From Path (type path)", value="path"),
            questionary.Choice("Back", value="back"),
        ],
        instruction=instruction,
        erase_when_done=True,
    ))
    if method == "back":
        return None

    if method == "browse":
        try:
            path = browse_file()
        except FileNotFoundError:
            console.print("[yellow]File dialog unavailable — enter path instead.[/yellow]")
        else:
            if path is None:
                raise UserCancelled
            return path

    return ask(questionary.text(
        "CSV file path:", instruction=instruction, erase_when_done=True
    ))


def read_csv_rows(path: str, required_columns: tuple[str, ...]) -> list[dict] | None:
    """Read CSV rows, checking required columns exist.
    Input: path (str), required_columns (tuple[str, ...]).
    Output: (list[dict] | None) row dicts, or None if columns missing.
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required_columns if c not in (reader.fieldnames or [])]
        if missing:
            console.print(f"[red]CSV missing columns: {', '.join(missing)}[/red]")
            return None
        return list(reader)


def _validate_row(row: dict, line: int) -> dict | None:
    """Validate one CSV row with the same rules as single-entry add.
    Input: row (dict), line (int) - 1-indexed CSV line number (for error messages).
    Output: (dict | None) entry with hours, or None if blank/invalid (errors printed for invalid rows).
    """
    if not any((row.get(col) or "").strip() for col in REQUIRED_COLUMNS):
        return None

    errors = []

    if validate_date(row["date"]) is not True:
        errors.append(f"date {validate_date(row['date'])}")

    start = parse_time(row["startTime"])
    if start is None:
        errors.append("startTime invalid format")

    end = parse_time(row["endTime"])
    if end is None:
        errors.append("endTime invalid format")

    if start and end and minutes(end) - minutes(start) < 60:
        errors.append("endTime must be at least 1 hour after startTime")

    if validate_work(row["work"]) is not True:
        errors.append(validate_work(row["work"]))

    if errors:
        console.print(f"[red]Row {line}: {'; '.join(errors)}[/red]")
        return None

    hours = (minutes(end) - minutes(start)) / 60
    return {"date": row["date"], "work": row["work"], "time_start": start, "time_end": end, "hours": hours}


def add_bulk_works(course_id: int) -> None:
    """Full bulk-import flow: pick CSV, validate rows, show summary, confirm, submit each.
    Input: course_id (int).
    """
    path = select_csv_path()
    if path is None:
        return

    try:
        rows = read_csv_rows(path, REQUIRED_COLUMNS)
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
        return
    if not rows:
        return

    entries = [entry for i, row in enumerate(rows, start=2) if (entry := _validate_row(row, i))]
    if not entries:
        console.print("[yellow]No valid rows to submit.[/yellow]")
        return

    console.print("\n[bold]Summary[/bold]")
    for e in entries:
        line = f"{e['date']} | {e['time_start']} - {e['time_end']} ({e['hours']:g} hrs) | {e['work']}"
        if e["hours"] % 1 != 0:
            line += "  [yellow][!] not a whole number of hours[/yellow]"
        if overlaps_lunch(e["time_start"], e["time_end"]):
            line += "  [yellow][!] overlaps lunch break (12:00-13:00)[/yellow]"
        console.print(line)
    total_hours = sum(e["hours"] for e in entries)
    console.print(f"\n[bold]Total: {total_hours:g} hrs across {len(entries)} work(s)[/bold]\n")

    if not confirm_or_cancel(f"Submit {len(entries)} valid work(s)?"):
        return

    added, failed = 0, 0
    for entry in entries:
        try:
            submit_work(course_id, entry)
        except Exception as e:
            failed += 1
            console.print(f"[red]Failed to add {entry['date']}: {e}[/red]")
            continue
        added += 1
        console.print(
            f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - "
            f"{entry['time_end']} | {entry['work']}"
        )

    console.print(f"[bold green]Added {added} work(s).[/bold green]" + (f" [red]{failed} failed.[/red]" if failed else ""))

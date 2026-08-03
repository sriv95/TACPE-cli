"""Bulk-import work entries from a CSV file, submitted one at a time with retry."""

import csv
import subprocess
import time
import urllib.error

import questionary
from rich.console import Console

from src.exceptions import UserCancelled
from src.works import minutes, parse_time, submit_work, validate_date, validate_work

console = Console()

REQUIRED_COLUMNS = ("date", "startTime", "endTime", "work")
RETRY_WAITS = (1, 5, 10, 30)

CSV_INSTRUCTION = (
    "\n  Required columns: date, startTime, endTime, work (other columns are ignored)"
    "\n  date: YYYY-MM-DD"
    "\n  startTime/endTime: HH:MM, HHMM, H, or H.mm (minutes must be 00 or 30)"
    "\n  Example:"
    "\n    date,startTime,endTime,work"
    "\n    2026-07-04,10:00,14:00,Grading Assignment 1\n"
)


def _browse_file() -> str | None:
    script = 'POSIX path of (choose file with prompt "Select CSV file" of type {"csv"})'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def select_csv_path() -> str | None:
    method = questionary.select(
        "Add bulk works - CSV file:",
        choices=[
            questionary.Choice("1. From file... (browse)", value="browse"),
            questionary.Choice("2. From Path (type path)", value="path"),
            questionary.Choice("Back", value="back"),
        ],
        instruction=CSV_INSTRUCTION,
        erase_when_done=True,
    ).ask()
    if method is None:
        raise UserCancelled
    if method == "back":
        return None

    if method == "browse":
        try:
            path = _browse_file()
        except FileNotFoundError:
            console.print("[yellow]File dialog unavailable (osascript not found) — enter path instead.[/yellow]")
        else:
            if path is None:
                raise UserCancelled
            return path

    path = questionary.text(
        "CSV file path:", instruction=CSV_INSTRUCTION, erase_when_done=True
    ).ask()
    if path is None:
        raise UserCancelled
    return path


def _read_rows(path: str) -> list[dict] | None:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            console.print(f"[red]CSV missing columns: {', '.join(missing)}[/red]")
            return None
        return list(reader)


def _validate_row(row: dict, line: int) -> dict | None:
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


def _submit_with_retry(course_id: int, entry: dict) -> None:
    wait_index = 0
    while True:
        try:
            submit_work(course_id, entry)
            return
        except urllib.error.URLError as e:
            wait = RETRY_WAITS[min(wait_index, len(RETRY_WAITS) - 1)]
            console.print(f"[red]Error: {e} — retrying in {wait}s[/red]")
            time.sleep(wait)
            wait_index += 1


def add_bulk_works(course_id: int) -> None:
    path = select_csv_path()
    if path is None:
        return

    try:
        rows = _read_rows(path)
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
        return
    if not rows:
        return

    entries = [entry for i, row in enumerate(rows, start=2) if (entry := _validate_row(row, i))]
    if not entries:
        console.print("[yellow]No valid rows to submit.[/yellow]")
        return

    lines = []
    for e in entries:
        line = f"  {e['date']} | {e['time_start']} - {e['time_end']} ({e['hours']:g} hrs) | {e['work']}"
        if e["hours"] % 1 != 0:
            line += "  [!] not a whole number of hours"
        lines.append(line)
    summary = "\n" + "\n".join(lines) + "\n"

    confirmed = questionary.confirm(
        f"Submit {len(entries)} valid work(s)?", instruction=summary, erase_when_done=True
    ).ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    for entry in entries:
        _submit_with_retry(course_id, entry)
        console.print(
            f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - "
            f"{entry['time_end']} | {entry['work']}"
        )

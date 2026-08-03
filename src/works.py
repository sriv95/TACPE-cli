"""Fetch and browse work-report entries for a selected course."""

import json
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import questionary
from rich.console import Console

from src.const import ADD_WORK_URL, WORK_REPORT_URL
from src.exceptions import UserCancelled
from src.request import request

UTC = ZoneInfo("UTC")

console = Console()

ADD_WORKS = object()
EXIT_APP = object()

BANGKOK = ZoneInfo("Asia/Bangkok")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch_works(course_id: int) -> list[dict]:
    data = json.loads(request(f"{WORK_REPORT_URL}?courseId={course_id}"))
    return data["workReport"]["works"]


def _to_utc_date(date_str: str) -> str:
    local_midnight = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BANGKOK)
    return local_midnight.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def submit_work(course_id: int, entry: dict) -> None:
    payload = {
        "courseId": course_id,
        "work": entry["work"],
        "date": _to_utc_date(entry["date"]),
        "time": f"{entry['time_start'].replace(':', '')}-{entry['time_end'].replace(':', '')}",
    }
    request(
        ADD_WORK_URL,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


def format_date(date_str: str) -> str:
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(BANGKOK)
    return dt.strftime("%Y-%m-%d")


def format_time(time_str: str) -> str:
    start, end = time_str.split("-")
    start_minutes = int(start[:2]) * 60 + int(start[2:])
    end_minutes = int(end[:2]) * 60 + int(end[2:])
    hours = (end_minutes - start_minutes) / 60
    return f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]} ({hours:g} hrs)"


def view_works(course_id: int) -> None:
    while True:
        works = fetch_works(course_id)

        choices = [
            questionary.Choice(
                f"{format_date(w['date'])} | {format_time(w['time'])} | {w['work']}", value=w["_id"]
            )
            for w in works
        ]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("Add works", value=ADD_WORKS))
        choices.append(questionary.Choice("Exit App", value=EXIT_APP))

        selected = questionary.select(
            "Works:", choices=choices, default=choices[-2], erase_when_done=True
        ).ask()
        if selected is None:
            raise UserCancelled
        if selected is ADD_WORKS:
            add_works_menu(course_id)
        elif selected is EXIT_APP:
            sys.exit(0)
        else:
            console.print("[yellow]Not implemented yet.[/yellow]")


def add_works_menu(course_id: int) -> None:
    choice = questionary.select(
        "Add works:",
        choices=[
            questionary.Choice("1. Add a work", value="single"),
            questionary.Choice("2. Add bulk works (.csv)", value="bulk"),
            questionary.Choice("Back", value="back"),
        ],
        erase_when_done=True,
    ).ask()
    if choice is None:
        raise UserCancelled
    if choice == "single":
        add_works(course_id)
    elif choice == "bulk":
        console.print("[yellow]Not implemented yet.[/yellow]")


def _validate_date(text: str) -> bool | str:
    return True if DATE_RE.match(text) else "Format: YYYY-MM-DD"


def _validate_work(text: str) -> bool | str:
    return True if text.strip() else "Work must not be empty"


def _parse_time(text: str) -> str | None:
    text = text.strip()
    hour = minute = None
    if ":" in text:
        m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", text)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
    elif "." in text:
        try:
            value = float(text)
        except ValueError:
            value = None
        if value is not None:
            hour, minute = int(value), round((value - int(value)) * 60)
    elif text.isdigit():
        padded = text.zfill(4) if len(text) > 2 else text.zfill(2) + "00"
        if len(padded) == 4:
            hour, minute = int(padded[:2]), int(padded[2:])

    if hour is None or not (0 <= hour <= 23) or minute not in (0, 30):
        return None
    return f"{hour:02d}:{minute:02d}"


def _validate_time(text: str) -> bool | str:
    return (
        True
        if _parse_time(text)
        else "Format: HH:MM, HHMM, H, or H.mm - minutes must be 00 or 30 (e.g. 17:30, 1730, 17, 17.5)"
    )


def _minutes(time_str: str) -> int:
    hour, minute = time_str.split(":")
    return int(hour) * 60 + int(minute)


def _validate_time_end(text: str, start: str) -> bool | str:
    valid = _validate_time(text)
    if valid is not True:
        return valid
    if _minutes(_parse_time(text)) - _minutes(start) < 60:
        return "End time must be at least 1 hour after start time"
    return True


def _prompt_work_entry() -> dict:
    date_str = questionary.text(
        "Add a Work - Enter Date (YYYY-MM-DD):",
        default=datetime.now(BANGKOK).strftime("%Y-%m-%d"),
        validate=_validate_date,
        erase_when_done=True,
    ).ask()
    if date_str is None:
        raise UserCancelled

    work = questionary.text(
        "Add a Work - Enter Work:",
        instruction=f"\n  Date: {date_str}\n",
        validate=_validate_work,
        erase_when_done=True,
    ).ask()
    if work is None:
        raise UserCancelled

    time_start = questionary.text(
        "Add a Work - Enter Start Time (HH:MM):",
        instruction=f"\n  Date: {date_str}\n  Work: {work}\n",
        validate=_validate_time,
        erase_when_done=True,
    ).ask()
    if time_start is None:
        raise UserCancelled
    time_start = _parse_time(time_start)

    time_end = questionary.text(
        "Add a Work - Enter End Time (HH:MM):",
        instruction=f"\n  Date: {date_str}\n  Work: {work}\n  Start: {time_start}\n",
        validate=lambda text: _validate_time_end(text, time_start),
        erase_when_done=True,
    ).ask()
    if time_end is None:
        raise UserCancelled
    time_end = _parse_time(time_end)

    start_minutes = int(time_start[:2]) * 60 + int(time_start[3:])
    end_minutes = int(time_end[:2]) * 60 + int(time_end[3:])
    hours = (end_minutes - start_minutes) / 60

    return {"date": date_str, "work": work, "time_start": time_start, "time_end": time_end, "hours": hours}


def add_works(course_id: int) -> None:
    entry = _prompt_work_entry()

    console.print("\n[bold]Summary[/bold]")
    console.print(f"{entry['date']} | {entry['time_start']} - {entry['time_end']} ({entry['hours']:g} hrs) | {entry['work']}")
    if entry["hours"] % 1 != 0:
        console.print(f"[yellow]Warning: {entry['hours']:g} hrs is not a whole number of hours.[/yellow]")

    confirmed = questionary.confirm("Submit this work?", erase_when_done=True).ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    submit_work(course_id, entry)
    console.print(
        f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}"
    )



"""Fetch and browse work-report entries for a selected course."""

import json
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import questionary
from rich.console import Console

from src.const import WORK_REPORT_URL
from src.exceptions import UserCancelled
from src.request import request

console = Console()

ADD_WORKS = object()
EXIT_APP = object()

BANGKOK = ZoneInfo("Asia/Bangkok")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def fetch_works(course_id: int) -> list[dict]:
    data = json.loads(request(f"{WORK_REPORT_URL}?courseId={course_id}"))
    return data["workReport"]["works"]


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
            add_works_menu()
        elif selected is EXIT_APP:
            sys.exit(0)
        else:
            console.print("[yellow]Not implemented yet.[/yellow]")


def add_works_menu() -> None:
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
        add_works()
    elif choice == "bulk":
        console.print("[yellow]Not implemented yet.[/yellow]")


def _validate_date(text: str) -> bool | str:
    return True if DATE_RE.match(text) else "Format: YYYY-MM-DD"


def _validate_time(text: str) -> bool | str:
    return True if TIME_RE.match(text) else "Format: HH:MM (24h)"


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
        "Add a Work - Enter Work:", instruction=f"\n  Date: {date_str}\n", erase_when_done=True
    ).ask()
    if work is None:
        raise UserCancelled
    if not work:
        raise RuntimeError("Work description required.")

    time_start = questionary.text(
        "Add a Work - Enter Start Time (HH:MM):",
        instruction=f"\n  Date: {date_str}\n  Work: {work}\n",
        validate=_validate_time,
        erase_when_done=True,
    ).ask()
    if time_start is None:
        raise UserCancelled

    time_end = questionary.text(
        "Add a Work - Enter End Time (HH:MM):",
        instruction=f"\n  Date: {date_str}\n  Work: {work}\n  Start: {time_start}\n",
        validate=_validate_time,
        erase_when_done=True,
    ).ask()
    if time_end is None:
        raise UserCancelled

    start_minutes = int(time_start[:2]) * 60 + int(time_start[3:])
    end_minutes = int(time_end[:2]) * 60 + int(time_end[3:])
    hours = (end_minutes - start_minutes) / 60

    return {"date": date_str, "work": work, "time_start": time_start, "time_end": time_end, "hours": hours}


def add_works() -> None:
    entries = []
    while True:
        entries.append(_prompt_work_entry())

        add_more = questionary.confirm("Add another work?", default=False).ask()
        if add_more is None:
            raise UserCancelled
        if not add_more:
            break

    console.print("\n[bold]Summary[/bold]")
    total_hours = 0.0
    for e in entries:
        console.print(f"{e['date']} | {e['time_start']} - {e['time_end']} ({e['hours']:g} hrs) | {e['work']}")
        total_hours += e["hours"]
    console.print(f"\n[bold]Total: {total_hours:g} hrs across {len(entries)} work(s)[/bold]\n")

    confirmed = questionary.confirm("Submit these works?").ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        console.print("[yellow]Cancelled.[/yellow]")
        return

    console.print("[yellow]Not implemented yet — submission API not wired up.[/yellow]")



"""Fetch and browse work-report entries for a selected course."""

import json
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
    console.print("[yellow]Not implemented yet.[/yellow]")

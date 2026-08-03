"""Fetch and browse work-report entries for a selected course."""

import json
import sys

import questionary
from rich.console import Console

from src.const import WORK_REPORT_URL
from src.exceptions import UserCancelled
from src.request import request

console = Console()

ADD_WORKS = object()
EXIT_APP = object()


def fetch_works(course_id: int) -> list[dict]:
    data = json.loads(request(f"{WORK_REPORT_URL}?courseId={course_id}"))
    return data["workReport"]["works"]


def view_works(course_id: int) -> None:
    works = fetch_works(course_id)

    choices = [
        questionary.Choice(f"{w['date'][:10]} | {w['time']} | {w['work']}", value=w["_id"])
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
        ],
        erase_when_done=True,
    ).ask()
    if choice is None:
        raise UserCancelled
    console.print("[yellow]Not implemented yet.[/yellow]")

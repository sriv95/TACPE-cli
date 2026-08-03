"""Course selection: fetch latest reg term, list TA courses, prompt user to pick one."""

import json

import questionary
from rich.console import Console

from src.const import REG_TIME_URL, TA_LIST_URL
from src.exceptions import UserCancelled
from src.request import request

console = Console()


def fetch_reg_times() -> list[dict]:
    """Fetch all academic year/term entries, newest first.
    Output: (list[dict]) {year, term, inUse} dicts.
    """
    data = json.loads(request(REG_TIME_URL))
    return sorted(data["regTimes"], key=lambda r: (r["year"], r["term"]), reverse=True)


def current_reg_time() -> tuple[int, int]:
    """Get the active academic term.
    Output: (tuple[int, int]) (year, term).
    """
    reg_times = fetch_reg_times()
    current = next((r for r in reg_times if r["inUse"]), reg_times[0])
    return current["year"], current["term"]


def select_reg_time() -> tuple[int, int]:
    """Prompt user to pick a year/term, defaulting to the active one.
    Output: (tuple[int, int]) (year, term).
    """
    reg_times = fetch_reg_times()

    choices = [
        questionary.Choice(
            f"{r['year']}/{r['term']}" + (" (current)" if r["inUse"] else ""),
            value=(r["year"], r["term"]),
        )
        for r in reg_times
    ]
    current = next((r for r in reg_times if r["inUse"]), None)
    default = (current["year"], current["term"]) if current else None

    reg_time = questionary.select(
        "Select year/term:", choices=choices, default=default, erase_when_done=True
    ).ask()
    if reg_time is None:
        raise UserCancelled
    return reg_time


def list_courses(reg_year: int, reg_term: int) -> list[dict]:
    """Fetch courses the user TAs for in a given term.
    Input: reg_year (int), reg_term (int).
    Output: (list[dict]) TA/course dicts.
    """
    url = f"{TA_LIST_URL}?regYear={reg_year}&regTerm={reg_term}"
    data = json.loads(request(url))
    return data["tas"]


CHANGE_REG_TIME = object()


def select_course() -> tuple[int, str]:
    """Prompt user to pick a course/section, with an option to change term.
    Output: (tuple[int, str]) (courseId, display label).
    """
    reg_year, reg_term = current_reg_time()

    while True:
        courses = list_courses(reg_year, reg_term)
        choices = [
            questionary.Choice(
                f"{ta['course']['courseTemplate']['courseNo']} "
                f"| Sec:{ta['course']['section']:03d} "
                f"| {ta['course']['courseTemplate']['courseName']}",
                value=ta["courseId"],
            )
            for ta in courses
        ]
        choices.append(
            questionary.Choice(f"Change academic term/year", value=CHANGE_REG_TIME)
        )

        course_id = questionary.select(
            f"Select course [{reg_term}/{reg_year}]:", choices=choices, erase_when_done=True
        ).ask()
        if course_id is None:
            raise UserCancelled
        if course_id is CHANGE_REG_TIME:
            reg_year, reg_term = select_reg_time()
            continue

        selected = next(ta for ta in courses if ta["courseId"] == course_id)
        label = (
            f"{selected['course']['courseTemplate']['courseNo']} "
            f"| Sec:{selected['course']['section']:03d} "
            f"| {selected['course']['courseTemplate']['courseName']}"
        )
        console.print(f"[bold green]Selected:[/bold green] {label}")
        return course_id, label

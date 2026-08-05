"""Course selection: fetch latest reg term, list TA courses, prompt user to pick one."""

import json
import sys

import questionary
from rich.console import Console

from src.func.const import REG_TIME_URL, TA_LIST_URL
from src.helper.exceptions import UserCancelled
from src.helper.prompt import ask
from src.func.request import request

console = Console()

BACK = object()
EXIT_APP = object()


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


def select_reg_time(reg_year: int, reg_term: int) -> tuple[int, int]:
    """Prompt user to pick a year/term, defaulting to the active one.
    Input: reg_year (int), reg_term (int) - currently selected term, kept if user picks Back.
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
    choices.append(questionary.Separator())
    choices.append(questionary.Choice("Back to select courses", value=BACK))
    current = next((r for r in reg_times if r["inUse"]), None)
    default = (current["year"], current["term"]) if current else None

    selected = ask(questionary.select(
        "Select year/term:", choices=choices, default=default, erase_when_done=True
    ))
    return (reg_year, reg_term) if selected is BACK else selected


def list_courses(reg_year: int, reg_term: int) -> list[dict]:
    """Fetch courses the user TAs for in a given term.
    Input: reg_year (int), reg_term (int).
    Output: (list[dict]) TA/course dicts.
    """
    url = f"{TA_LIST_URL}?regYear={reg_year}&regTerm={reg_term}"
    data = json.loads(request(url))
    return data["tas"]


CHANGE_REG_TIME = object()
CHECK_OVERLAP = object()
LOGOUT = object()


def select_course() -> tuple[int, str]:
    """Prompt user to pick a course/section, with options to change term or check overlaps.
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
        choices.append(questionary.Separator())
        choices.append(
            questionary.Choice(f"Change academic term/year", value=CHANGE_REG_TIME)
        )
        choices.append(questionary.Choice("Check Overlap", value=CHECK_OVERLAP))
        choices.append(questionary.Choice("Logout (remove Cookie)", value=LOGOUT))
        choices.append(questionary.Choice("Exit App", value=EXIT_APP))

        course_id = ask(questionary.select(
            f"Select course [{reg_term}/{reg_year}]:", choices=choices, erase_when_done=True
        ))
        if course_id is CHANGE_REG_TIME:
            reg_year, reg_term = select_reg_time(reg_year, reg_term)
            continue
        if course_id is CHECK_OVERLAP:
            from src.cli.work.auto_slot import check_overlap_all_courses

            check_overlap_all_courses(reg_year, reg_term)
            continue
        if course_id is LOGOUT:
            from src.cli.auth import logout

            logout()
            raise UserCancelled
        if course_id is EXIT_APP:
            sys.exit(0)

        selected = next(ta for ta in courses if ta["courseId"] == course_id)
        label = (
            f"{selected['course']['courseTemplate']['courseNo']} "
            f"| Sec:{selected['course']['section']:03d} "
            f"| {selected['course']['courseTemplate']['courseName']}"
        )
        console.print(f"[bold green]Selected:[/bold green] {label}")
        return course_id, label

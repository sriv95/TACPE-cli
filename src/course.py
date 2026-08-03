"""Course selection: fetch latest reg term, list TA courses, prompt user to pick one."""

import json

import questionary

from src.const import REG_TIME_URL, TA_LIST_URL
from src.exceptions import UserCancelled
from src.request import request


def latest_reg_time() -> tuple[int, int]:
    data = json.loads(request(REG_TIME_URL))
    reg_times = sorted(data["regTimes"], key=lambda r: (r["year"], r["term"]))
    latest = reg_times[-1]
    return latest["year"], latest["term"]


def list_courses(reg_year: int, reg_term: int) -> list[dict]:
    url = f"{TA_LIST_URL}?regYear={reg_year}&regTerm={reg_term}"
    data = json.loads(request(url))
    return data["tas"]


def select_course() -> int:
    reg_year, reg_term = latest_reg_time()
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
    course_id = questionary.select(f"Select course [{reg_term}/{reg_year}]:", choices=choices).ask()
    if course_id is None:
        raise UserCancelled
    return course_id

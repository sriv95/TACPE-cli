"""Fetch and browse work-report entries for a selected course."""

import json
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import questionary
from rich.console import Console

from src.const import ADD_WORK_URL, DELETE_WORK_URL, EDIT_WORK_URL, WORK_REPORT_URL
from src.exceptions import UserCancelled
from src.request import post_json, request

UTC = ZoneInfo("UTC")

console = Console()

ADD_WORKS = object()
EXIT_APP = object()

BANGKOK = ZoneInfo("Asia/Bangkok")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch_works(course_id: int) -> list[dict]:
    """Fetch existing work entries for a course.
    Input: course_id (int).
    Output: (list[dict]) work dicts.
    """
    data = json.loads(request(f"{WORK_REPORT_URL}?courseId={course_id}"))
    return data["workReport"]["works"]


def _to_utc_date(date_str: str) -> str:
    """Convert a Bangkok-local date into the API's UTC ISO format.
    Input: date_str (str) - YYYY-MM-DD (Bangkok).
    Output: (str) ISO UTC timestamp.
    """
    local_midnight = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=BANGKOK)
    return local_midnight.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _work_payload(course_id: int, entry: dict) -> dict:
    """Build the courseId/work/date/time payload shared by add and edit.
    Input: course_id (int), entry (dict) - date/work/time_start/time_end.
    Output: (dict) payload.
    """
    return {
        "courseId": course_id,
        "work": entry["work"],
        "date": _to_utc_date(entry["date"]),
        "time": f"{entry['time_start'].replace(':', '')}-{entry['time_end'].replace(':', '')}",
    }


def submit_work(course_id: int, entry: dict) -> None:
    """POST a new work entry to the API.
    Input: course_id (int), entry (dict) - date/work/time_start/time_end.
    """
    post_json(ADD_WORK_URL, _work_payload(course_id, entry))


def edit_work(course_id: int, work_id: str, entry: dict) -> None:
    """POST an edit for an existing work entry.
    Input: course_id (int), work_id (str), entry (dict) - date/work/time_start/time_end.
    """
    payload = _work_payload(course_id, entry)
    payload["workId"] = work_id
    post_json(EDIT_WORK_URL, payload)


def delete_work(course_id: int, work_id: str) -> None:
    """POST a deletion for an existing work entry.
    Input: course_id (int), work_id (str).
    """
    post_json(DELETE_WORK_URL, {"courseId": course_id, "workId": work_id})


def format_date(date_str: str) -> str:
    """Convert an API UTC date to a Bangkok-local display date.
    Input: date_str (str) - ISO UTC timestamp.
    Output: (str) YYYY-MM-DD.
    """
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(BANGKOK)
    return dt.strftime("%Y-%m-%d")


def format_time(time_str: str) -> str:
    """Render API time range for display.
    Input: time_str (str) - HHMM-HHMM.
    Output: (str) 'HH:MM - HH:MM (N hrs)'.
    """
    start, end = time_str.split("-")
    start_min = int(start[:2]) * 60 + int(start[2:])
    end_min = int(end[:2]) * 60 + int(end[2:])
    hours = (end_min - start_min) / 60
    return f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]} ({hours:g} hrs)"


def view_works(course_id: int, course_label: str) -> None:
    """Main works loop: list entries, offer Add works / Exit.
    Input: course_id (int), course_label (str) - display label.
    """
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
            "Works:",
            choices=choices,
            default=choices[-2],
            instruction=f"\n  Course: {course_label}\n",
            erase_when_done=True,
        ).ask()
        if selected is None:
            raise UserCancelled
        if selected is ADD_WORKS:
            add_works_menu(course_id)
        elif selected is EXIT_APP:
            sys.exit(0)
        else:
            work = next(w for w in works if w["_id"] == selected)
            work_entry_menu(course_id, work)


def work_entry_menu(course_id: int, work: dict) -> None:
    """Prompt user to Edit/Delete/Back for a selected work entry.
    Input: course_id (int), work (dict) - the selected work entry.
    """
    choice = questionary.select(
        "Work entry:",
        choices=[
            questionary.Choice("Edit", value="edit"),
            questionary.Choice("Delete", value="delete"),
            questionary.Choice("Back", value="back"),
        ],
        instruction=f"\n  {format_date(work['date'])} | {format_time(work['time'])} | {work['work']}\n",
        erase_when_done=True,
    ).ask()
    if choice is None:
        raise UserCancelled
    if choice == "edit":
        edit_work_entry(course_id, work)
    elif choice == "delete":
        delete_work_entry(course_id, work)


def add_works_menu(course_id: int) -> None:
    """Prompt user to choose single/bulk add, or go back.
    Input: course_id (int).
    """
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
        from src.bulk_works import add_bulk_works

        add_bulk_works(course_id)


def validate_date(text: str) -> bool | str:
    """Check date format for questionary.
    Input: text (str) - raw input.
    Output: (bool | str) True, or an error message.
    """
    return True if DATE_RE.match(text) else "Format: YYYY-MM-DD"


def validate_work(text: str) -> bool | str:
    """Check task text is non-empty for questionary.
    Input: text (str) - raw input.
    Output: (bool | str) True, or an error message.
    """
    return True if text.strip() else "Task must not be empty"


def parse_time(text: str) -> str | None:
    """Parse flexible time input (HH:MM, HHMM, H, H.mm) into normalized HH:MM.
    Input: text (str) - raw input.
    Output: (str | None) 'HH:MM', or None if invalid or minutes not 00/30.
    """
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
    """Check time text parses for questionary.
    Input: text (str) - raw input.
    Output: (bool | str) True, or an error message.
    """
    return (
        True
        if parse_time(text)
        else "Format: HH:MM, HHMM, H, or H.mm - minutes must be 00 or 30 (e.g. 17:30, 1730, 17, 17.5)"
    )


def minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight.
    Input: time_str (str) - 'HH:MM'.
    Output: (int) minutes.
    """
    hour, minute = time_str.split(":")
    return int(hour) * 60 + int(minute)


def overlaps_lunch(time_start: str, time_end: str) -> bool:
    """Check if a time range overlaps the 12:00-13:00 lunch break.
    Input: time_start (str), time_end (str) - 'HH:MM'.
    Output: (bool).
    """
    return minutes(time_start) < minutes("13:00") and minutes(time_end) > minutes("12:00")


def _validate_time_end(text: str, start: str) -> bool | str:
    """Check end time is valid and >=1hr after start, for questionary.
    Input: text (str) - raw end-time input, start (str) - parsed 'HH:MM'.
    Output: (bool | str) True, or an error message.
    """
    valid = _validate_time(text)
    if valid is not True:
        return valid
    if minutes(parse_time(text)) - minutes(start) < 60:
        return "End time must be at least 1 hour after start time"
    return True


def _prompt_work_entry(label: str = "Add a Work", defaults: dict | None = None) -> dict:
    """Prompt user through date/task/start/end time for one entry.
    Input: label (str) - prompt prefix, defaults (dict | None) - prefill date/work/time_start/time_end.
    Output: (dict) entry with hours.
    """
    defaults = defaults or {}
    date_str = questionary.text(
        f"{label} - Enter Date (YYYY-MM-DD):",
        default=defaults.get("date", datetime.now(BANGKOK).strftime("%Y-%m-%d")),
        validate=validate_date,
        erase_when_done=True,
    ).ask()
    if date_str is None:
        raise UserCancelled

    work = questionary.text(
        f"{label} - Enter Task:",
        default=defaults.get("work", ""),
        instruction=f"\n  Date: {date_str}\n",
        validate=validate_work,
        erase_when_done=True,
    ).ask()
    if work is None:
        raise UserCancelled

    time_start = questionary.text(
        f"{label} - Enter Start Time (HH:MM):",
        default=defaults.get("time_start", ""),
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n",
        validate=_validate_time,
        erase_when_done=True,
    ).ask()
    if time_start is None:
        raise UserCancelled
    time_start = parse_time(time_start)

    time_end = questionary.text(
        f"{label} - Enter End Time (HH:MM):",
        default=defaults.get("time_end", ""),
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n  Start: {time_start}\n",
        validate=lambda text: _validate_time_end(text, time_start),
        erase_when_done=True,
    ).ask()
    if time_end is None:
        raise UserCancelled
    time_end = parse_time(time_end)

    start_min = int(time_start[:2]) * 60 + int(time_start[3:])
    end_min = int(time_end[:2]) * 60 + int(time_end[3:])
    hours = (end_min - start_min) / 60

    return {"date": date_str, "work": work, "time_start": time_start, "time_end": time_end, "hours": hours}


def _summarize(entry: dict) -> str:
    """Build a summary string with warnings for a prompted entry.
    Input: entry (dict) - date/work/time_start/time_end/hours.
    Output: (str) summary.
    """
    summary = (
        f"\n{entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}\n"
    )
    if entry["hours"] % 1 != 0:
        summary += f"  Warning: {entry['hours']:g} hrs is not a whole number of hours.\n"
    if overlaps_lunch(entry["time_start"], entry["time_end"]):
        summary += "  Warning: overlaps lunch break (12:00-13:00).\n"
    return summary


def add_works(course_id: int) -> None:
    """Collect one work entry, show summary/warnings, confirm, and submit.
    Input: course_id (int).
    """
    entry = _prompt_work_entry()

    confirmed = questionary.confirm(
        "Submit this work? (Y/n)", instruction=_summarize(entry), erase_when_done=True
    ).ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    submit_work(course_id, entry)
    console.print(
        f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}"
    )


def edit_work_entry(course_id: int, work: dict) -> None:
    """Prompt with prefilled values, show summary/warnings, confirm, and submit an edit.
    Input: course_id (int), work (dict) - the existing work entry.
    """
    start, end = work["time"].split("-")
    defaults = {
        "date": format_date(work["date"]),
        "work": work["work"],
        "time_start": f"{start[:2]}:{start[2:]}",
        "time_end": f"{end[:2]}:{end[2:]}",
    }
    entry = _prompt_work_entry(label="Edit Work", defaults=defaults)

    confirmed = questionary.confirm(
        "Submit this edit? (Y/n)", instruction=_summarize(entry), erase_when_done=True
    ).ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    edit_work(course_id, work["_id"], entry)
    console.print(
        f"[bold green]Updated:[/bold green] {entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}"
    )


def delete_work_entry(course_id: int, work: dict) -> None:
    """Confirm and delete an existing work entry.
    Input: course_id (int), work (dict) - the existing work entry.
    """
    confirmed = questionary.confirm(
        "Delete this work? (y/N)",
        default=False,
        instruction=f"\n  {format_date(work['date'])} | {format_time(work['time'])} | {work['work']}\n",
        erase_when_done=True,
    ).ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    delete_work(course_id, work["_id"])
    console.print(f"[bold red]Deleted:[/bold red] {format_date(work['date'])} | {work['work']}")


def _demo() -> None:
    """Self-check: payload building and edit-prefill time parsing (no network)."""
    entry = {"date": "2026-08-03", "work": "tests", "time_start": "00:30", "time_end": "03:00", "hours": 2.5}
    payload = _work_payload(1, entry)
    assert payload["time"] == "0030-0300"
    assert payload["date"].endswith("Z")

    work = {"_id": "w1", "date": payload["date"], "work": "tests", "time": "0030-0300"}
    start, end = work["time"].split("-")
    assert f"{start[:2]}:{start[2:]}" == "00:30"
    assert f"{end[:2]}:{end[2:]}" == "03:00"


if __name__ == "__main__":
    _demo()
    print("OK")



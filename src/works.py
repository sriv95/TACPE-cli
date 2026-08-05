"""Fetch and browse work-report entries for a selected course."""

import json
import re
import sys
import webbrowser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import questionary
from rich.console import Console

from src.const import ADD_WORK_URL, BASE_URL, DELETE_WORK_URL, EDIT_WORK_URL, WORK_REPORT_URL
from src.prompt import ask, confirm_or_cancel
from src.request import post_json, request

UTC = ZoneInfo("UTC")

console = Console()

ADD_WORKS = object()
MORE_OPTIONS = object()
BACK_TO_COURSES = object()
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


def _month_range(anchor_date: str) -> tuple[str, str]:
    """Compute the [1st-of-last-month-relative-to-anchor, today] date bound.
    Input: anchor_date (str) - YYYY-MM-DD, whose month determines the lower bound.
    Output: (tuple[str, str]) (min_date, max_date) as YYYY-MM-DD.
    """
    anchor = datetime.strptime(anchor_date, "%Y-%m-%d")
    first_of_anchor_month = anchor.replace(day=1)
    last_month_end = first_of_anchor_month - timedelta(days=1)
    min_date = last_month_end.replace(day=1).strftime("%Y-%m-%d")
    max_date = datetime.now(BANGKOK).strftime("%Y-%m-%d")
    return min_date, max_date


def _weekly_dates(selected_date: str, min_date: str, max_date: str) -> list[str]:
    """List dates sharing selected_date's weekday, 7 days apart, within [min_date, max_date], newest first.
    Input: selected_date, min_date, max_date (str) - YYYY-MM-DD.
    Output: (list[str]) dates, newest first, includes selected_date.
    """
    anchor = datetime.strptime(selected_date, "%Y-%m-%d")
    lo = datetime.strptime(min_date, "%Y-%m-%d")
    hi = datetime.strptime(max_date, "%Y-%m-%d")

    step = anchor
    while step <= hi:
        step += timedelta(days=7)
    step -= timedelta(days=7)

    dates = []
    while step >= lo:
        dates.append(step.strftime("%Y-%m-%d"))
        step -= timedelta(days=7)
    return dates


def _daily_dates(min_date: str, max_date: str) -> list[str]:
    """List every calendar date within [min_date, max_date], newest first.
    Input: min_date, max_date (str) - YYYY-MM-DD.
    Output: (list[str]) dates, newest first, inclusive of both bounds.
    """
    lo = datetime.strptime(min_date, "%Y-%m-%d")
    hi = datetime.strptime(max_date, "%Y-%m-%d")

    dates = []
    step = hi
    while step >= lo:
        dates.append(step.strftime("%Y-%m-%d"))
        step -= timedelta(days=1)
    return dates


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
        choices.append(questionary.Choice("More Options", value=MORE_OPTIONS))
        choices.append(questionary.Choice("Back to select courses", value=BACK_TO_COURSES))
        choices.append(questionary.Choice("Exit App", value=EXIT_APP))

        selected = ask(questionary.select(
            "Works:",
            choices=choices,
            default=choices[-4],
            instruction=f"\n  Course: {course_label}\n",
            erase_when_done=True,
        ))
        if selected is ADD_WORKS:
            add_works_menu(course_id)
        elif selected is MORE_OPTIONS:
            more_options_menu(course_id, works)
        elif selected is BACK_TO_COURSES:
            return
        elif selected is EXIT_APP:
            sys.exit(0)
        else:
            work = next(w for w in works if w["_id"] == selected)
            work_entry_menu(course_id, work)


def more_options_menu(course_id: int, works: list[dict]) -> None:
    """Prompt user for extra actions: multi-delete or back.
    Input: course_id (int), works (list[dict]) - current work entries.
    """
    choice = ask(questionary.select(
        "More Options:",
        choices=[
            questionary.Choice("Delete multiple", value="delete_multiple"),
            questionary.Choice("Open in Browser", value="open_browser"),
            questionary.Choice("Back", value="back"),
        ],
        erase_when_done=True,
    ))
    if choice == "delete_multiple":
        delete_multiple_works(course_id, works)
    elif choice == "open_browser":
        open_in_browser(course_id)


def open_in_browser(course_id: int) -> None:
    """Open the work report page in the default browser.
    Input: course_id (int).
    """
    webbrowser.open(f"{BASE_URL}/student/workReport/{course_id}")


def delete_multiple_works(course_id: int, works: list[dict]) -> None:
    """Checkbox-select entries and delete each, reporting per-item failures.
    Input: course_id (int), works (list[dict]) - current work entries.
    """
    if not works:
        console.print("[yellow]No works to delete.[/yellow]")
        return

    selected = ask(questionary.checkbox(
        "Select works to delete (space to toggle, enter to confirm):",
        choices=[
            questionary.Choice(
                f"{format_date(w['date'])} | {format_time(w['time'])} | {w['work']}", value=w["_id"]
            )
            for w in works
        ],
        erase_when_done=True,
    ))
    if not selected:
        return

    if not confirm_or_cancel(f"Delete {len(selected)} work(s)? (y/N)", default=False, erase_when_done=True):
        return

    by_id = {w["_id"]: w for w in works}
    deleted, failed = 0, 0
    for work_id in selected:
        try:
            delete_work(course_id, work_id)
        except Exception as e:
            failed += 1
            console.print(f"[red]Failed to delete {by_id[work_id]['work']}: {e}[/red]")
            continue
        deleted += 1

    console.print(f"[bold green]Deleted {deleted} work(s).[/bold green]" + (f" [red]{failed} failed.[/red]" if failed else ""))


def work_entry_menu(course_id: int, work: dict) -> None:
    """Prompt user to Edit/Delete/Back for a selected work entry.
    Input: course_id (int), work (dict) - the selected work entry.
    """
    choice = ask(questionary.select(
        "Work entry:",
        choices=[
            questionary.Choice("Edit", value="edit"),
            questionary.Choice("Clone", value="clone"),
            questionary.Choice("Delete", value="delete"),
            questionary.Choice("Back", value="back"),
        ],
        instruction=f"\n  {format_date(work['date'])} | {format_time(work['time'])} | {work['work']}\n",
        erase_when_done=True,
    ))
    if choice == "edit":
        edit_work_entry(course_id, work)
    elif choice == "clone":
        clone_work_entry(course_id, work)
    elif choice == "delete":
        delete_work_entry(course_id, work)


def add_works_menu(course_id: int) -> None:
    """Prompt user to choose single/bulk add, or go back.
    Input: course_id (int).
    """
    choice = ask(questionary.select(
        "Add works:",
        choices=[
            questionary.Choice("1. Add a work", value="single"),
            questionary.Choice("2. Add bulk works (.csv)", value="bulk"),
            questionary.Choice("3. Auto Find Slot", value="auto"),
            questionary.Choice("4. Auto Find Slot (bulk .csv)", value="auto_bulk"),
            questionary.Choice("Back", value="back"),
        ],
        erase_when_done=True,
    ))
    if choice == "single":
        add_works(course_id)
    elif choice == "bulk":
        from src.bulk_works import add_bulk_works

        add_bulk_works(course_id)
    elif choice == "auto":
        from src.auto_slot import auto_find_slot

        auto_find_slot(course_id)
    elif choice == "auto_bulk":
        from src.auto_slot import auto_find_slot_bulk

        auto_find_slot_bulk(course_id)


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


def parse_time(text: str, strict: bool = True) -> str | None:
    """Parse flexible time input (HH:MM, HHMM, H, H.mm) into normalized HH:MM.
    Input: text (str) - raw input, strict (bool) - if True, minutes must be 00/30.
    Output: (str | None) 'HH:MM', or None if invalid (or minutes not 00/30 when strict).
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

    if hour is None or not (0 <= hour <= 23) or minute is None or not (0 <= minute <= 59):
        return None
    if strict and minute not in (0, 30):
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


def _prompt_date(label: str, default: str, min_date: str | None = None, max_date: str | None = None) -> str:
    """Prompt for a date, optionally bounded to [min_date, max_date].
    Input: label (str) - prompt prefix, default (str) - prefill YYYY-MM-DD,
        min_date/max_date (str | None) - inclusive bound, or None to skip the range check.
    Output: (str) YYYY-MM-DD.
    """
    def _validate(text: str) -> bool | str:
        valid = validate_date(text)
        if valid is not True:
            return valid
        if min_date and max_date and not (min_date <= text <= max_date):
            return f"Format: YYYY-MM-DD (between {min_date} and {max_date})"
        return True

    return ask(questionary.text(
        f"{label} - Enter Date (YYYY-MM-DD):",
        default=default,
        validate=_validate,
        erase_when_done=True,
    ))


def _prompt_task_time(label: str, date_str: str, defaults: dict | None = None) -> dict:
    """Prompt user through task/start/end time for one entry.
    Input: label (str) - prompt prefix, date_str (str) - already-known date, shown for context,
        defaults (dict | None) - prefill work/time_start/time_end.
    Output: (dict) {work, time_start, time_end, hours}.
    """
    defaults = defaults or {}
    work = ask(questionary.text(
        f"{label} - Enter Task:",
        default=defaults.get("work", ""),
        instruction=f"\n  Date: {date_str}\n",
        validate=validate_work,
        erase_when_done=True,
    ))

    time_start = ask(questionary.text(
        f"{label} - Enter Start Time (HH:MM):",
        default=defaults.get("time_start", ""),
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n",
        validate=_validate_time,
        erase_when_done=True,
    ))
    time_start = parse_time(time_start)

    time_end = ask(questionary.text(
        f"{label} - Enter End Time (HH:MM):",
        default=defaults.get("time_end", ""),
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n  Start: {time_start}\n",
        validate=lambda text: _validate_time_end(text, time_start),
        erase_when_done=True,
    ))
    time_end = parse_time(time_end)

    hours = (minutes(time_end) - minutes(time_start)) / 60
    return {"work": work, "time_start": time_start, "time_end": time_end, "hours": hours}


def _prompt_work_entry(label: str = "Add a Work", defaults: dict | None = None) -> dict:
    """Prompt user through date/task/start/end time for one entry.
    Input: label (str) - prompt prefix, defaults (dict | None) - prefill date/work/time_start/time_end.
    Output: (dict) entry with hours.
    """
    defaults = defaults or {}
    default_date = defaults.get("date", datetime.now(BANGKOK).strftime("%Y-%m-%d"))
    date_str = _prompt_date(label, default_date)
    task_time = _prompt_task_time(label, date_str, defaults)
    return {"date": date_str, **task_time}


def prompt_weekly_until(selected_date: str, min_date: str, max_date: str) -> list[str]:
    """Prompt for a weekly-repeat cutoff via select, cursor starting on selected_date.
    Input: selected_date, min_date, max_date (str) - YYYY-MM-DD.
    Output: (list[str]) dates between selected_date and the chosen cutoff (inclusive), newest first.
    """
    weekdays = _weekly_dates(selected_date, min_date, max_date)

    def _label(d: str) -> str:
        weekday = datetime.strptime(d, "%Y-%m-%d").strftime("%a")
        tag = " (today)" if d == max_date else " (1st of last month)" if d == min_date else ""
        return f"{d} ({weekday}){tag}"

    choices = [questionary.Choice(_label(d), value=d) for d in weekdays]
    cutoff = ask(questionary.select(
        "Repeat weekly until:",
        choices=choices,
        default=next(c for c in choices if c.value == selected_date),
        erase_when_done=True,
    ))

    lo, hi = sorted([selected_date, cutoff])
    return [d for d in weekdays if lo <= d <= hi]


def prompt_multi_select_dates(selected_date: str, min_date: str, max_date: str) -> list[str]:
    """Checkbox-select dates, selected_date pre-checked with cursor starting there.
    Input: selected_date, min_date, max_date (str) - YYYY-MM-DD.
    Output: (list[str]) checked dates.
    """
    days = _daily_dates(min_date, max_date)

    def _label(d: str) -> str:
        tag = " (today)" if d == max_date else " (1st of last month)" if d == min_date else ""
        return f"{d}{tag}"

    choices = [
        questionary.Choice(_label(d), value=d, checked=(d == selected_date))
        for d in days
    ]
    return ask(questionary.checkbox(
        "Select dates (space to toggle, enter to confirm):",
        choices=choices,
        initial_choice=selected_date,
        erase_when_done=True,
    ))


def summarize_entry(entry: dict) -> str:
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
    if entry["hours"] > 4:
        summary += f"  Warning: {entry['hours']:g} hrs exceeds max 4 hours.\n"
    if overlaps_lunch(entry["time_start"], entry["time_end"]):
        summary += "  Warning: overlaps lunch break (12:00-13:00).\n"
    return summary


def summarize_entries(dates: list[str], task_time: dict) -> str:
    """Build a summary string (one row per date) with shared warnings, for a multi-date add.
    Input: dates (list[str]) - YYYY-MM-DD dates, task_time (dict) - work/time_start/time_end/hours.
    Output: (str) summary.
    """
    lines = [
        f"{d} | {task_time['time_start']} - {task_time['time_end']} "
        f"({task_time['hours']:g} hrs) | {task_time['work']}"
        for d in dates
    ]
    summary = "\n" + "\n".join(lines) + "\n"
    if task_time["hours"] % 1 != 0:
        summary += f"  Warning: {task_time['hours']:g} hrs is not a whole number of hours.\n"
    if task_time["hours"] > 4:
        summary += f"  Warning: {task_time['hours']:g} hrs exceeds max 4 hours.\n"
    if overlaps_lunch(task_time["time_start"], task_time["time_end"]):
        summary += "  Warning: overlaps lunch break (12:00-13:00).\n"
    return summary


def _prompt_more_dates(selected_date: str, today: str) -> list[str]:
    """Prompt for additional dates to add to the current batch: weekly-until, multi-select, or one more single date.
    Input: selected_date (str) - the original anchor date, today (str) - YYYY-MM-DD bound reference.
    Output: (list[str]) additional dates, or [] if the user chose Back.
    """
    mode = ask(questionary.select(
        "Add more:",
        choices=[
            questionary.Choice("Every week until date", value="weekly"),
            questionary.Choice("Multiple dates (multi-select)", value="multi"),
            questionary.Choice("Single date", value="single"),
            questionary.Choice("Back", value="back"),
        ],
        erase_when_done=True,
    ))
    if mode == "back":
        return []

    if mode == "single":
        return [_prompt_date("Add a Work", today)]

    list_min, list_max = _month_range(selected_date)
    if mode == "weekly":
        return prompt_weekly_until(selected_date, list_min, list_max)
    return prompt_multi_select_dates(selected_date, list_min, list_max)


def add_works(course_id: int) -> None:
    """Prompt for a date, shared task/time, then confirm/add-more/cancel, submit all.
    Input: course_id (int).
    """
    today = datetime.now(BANGKOK).strftime("%Y-%m-%d")
    step_min, step_max = _month_range(today)
    selected_date = _prompt_date("Add a Work", today, step_min, step_max)
    dates = [selected_date]

    task_time = _prompt_task_time("Add a Work", selected_date)

    while True:
        dates = sorted(set(dates), reverse=True)
        message = "Submit this work?" if len(dates) == 1 else f"Submit these {len(dates)} works?"
        action = ask(questionary.select(
            message,
            choices=[
                questionary.Choice("Submit", value="submit"),
                questionary.Choice("Add more dates", value="add_more"),
                questionary.Choice("Cancel", value="cancel"),
            ],
            instruction=summarize_entries(dates, task_time),
            erase_when_done=True,
        ))
        if action == "cancel":
            return
        if action == "submit":
            break
        dates = list(set(dates) | set(_prompt_more_dates(selected_date, today)))

    added, failed = 0, 0
    for date_str in dates:
        entry = {"date": date_str, **task_time}
        try:
            submit_work(course_id, entry)
        except Exception as e:
            failed += 1
            console.print(f"[red]Failed to add {date_str}: {e}[/red]")
            continue
        added += 1
        console.print(
            f"[bold green]Added:[/bold green] {date_str} | {task_time['time_start']} - {task_time['time_end']} "
            f"({task_time['hours']:g} hrs) | {task_time['work']}"
        )

    if len(dates) > 1:
        summary_line = f"[bold green]Added {added} work(s).[/bold green]"
        if failed:
            summary_line += f" [red]{failed} failed.[/red]"
        console.print(summary_line)


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

    if not confirm_or_cancel("Submit this edit? (Y/n)", instruction=summarize_entry(entry), erase_when_done=True):
        return

    edit_work(course_id, work["_id"], entry)
    console.print(
        f"[bold green]Updated:[/bold green] {entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}"
    )


def clone_work_entry(course_id: int, work: dict) -> None:
    """Prompt for a new date, reuse task/time from an existing entry, confirm, and submit.
    Input: course_id (int), work (dict) - the existing work entry to clone.
    """
    start, end = work["time"].split("-")
    date_str = ask(questionary.text(
        "Clone Work - Enter Date (YYYY-MM-DD):",
        default=datetime.now(BANGKOK).strftime("%Y-%m-%d"),
        instruction=f"\n  Task: {work['work']}\n  Time: {start[:2]}:{start[2:]} - {end[:2]}:{end[2:]}\n",
        validate=validate_date,
        erase_when_done=True,
    ))

    time_start = f"{start[:2]}:{start[2:]}"
    time_end = f"{end[:2]}:{end[2:]}"
    hours = (minutes(time_end) - minutes(time_start)) / 60
    entry = {"date": date_str, "work": work["work"], "time_start": time_start, "time_end": time_end, "hours": hours}

    if not confirm_or_cancel("Submit this work? (Y/n)", instruction=summarize_entry(entry), erase_when_done=True):
        return

    submit_work(course_id, entry)
    console.print(
        f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - {entry['time_end']} "
        f"({entry['hours']:g} hrs) | {entry['work']}"
    )


def delete_work_entry(course_id: int, work: dict) -> None:
    """Confirm and delete an existing work entry.
    Input: course_id (int), work (dict) - the existing work entry.
    """
    if not confirm_or_cancel(
        "Delete this work? (y/N)",
        default=False,
        instruction=f"\n  {format_date(work['date'])} | {format_time(work['time'])} | {work['work']}\n",
        erase_when_done=True,
    ):
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

    min_date, max_date = _month_range("2026-08-15")
    assert min_date == "2026-07-01"
    assert max_date == datetime.now(BANGKOK).strftime("%Y-%m-%d")

    min_date, _ = _month_range("2026-08-01")
    assert min_date == "2026-07-01"  # anchor on the 1st still uses the prior month

    min_date, _ = _month_range("2026-01-15")
    assert min_date == "2025-12-01"  # year rollover

    weekly = _weekly_dates("2026-07-20", "2026-06-01", "2026-08-04")
    assert weekly == [
        "2026-08-03", "2026-07-27", "2026-07-20", "2026-07-13", "2026-07-06",
        "2026-06-29", "2026-06-22", "2026-06-15", "2026-06-08", "2026-06-01",
    ]

    daily = _daily_dates("2026-06-01", "2026-06-03")
    assert daily == ["2026-06-03", "2026-06-02", "2026-06-01"]

    task_time = {"work": "tests", "time_start": "08:00", "time_end": "12:00", "hours": 4.0}
    summary = summarize_entries(["2026-07-20", "2026-07-13"], task_time)
    assert "2026-07-20 | 08:00 - 12:00 (4 hrs) | tests" in summary
    assert "2026-07-13 | 08:00 - 12:00 (4 hrs) | tests" in summary
    assert "Warning" not in summary  # exactly 4 hrs, no lunch overlap

    task_time_warn = {"work": "tests", "time_start": "11:00", "time_end": "15:30", "hours": 4.5}
    summary_warn = summarize_entries(["2026-07-20"], task_time_warn)
    assert "not a whole number" in summary_warn
    assert "overlaps lunch" in summary_warn


if __name__ == "__main__":
    _demo()
    print("OK")



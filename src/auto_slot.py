"""Auto Find Slot: find TA-work start times free of lunch, timetable, and existing works."""

import csv
from datetime import datetime

import questionary
from rich.console import Console

from src.bulk_works import select_csv_path
from src.course import current_reg_time, list_courses
from src.exceptions import UserCancelled
from src.timetable import entries_for_weekday, timetable_gate
from src.works import (
    fetch_works,
    format_date,
    minutes,
    parse_time,
    submit_work,
    summarize_entry,
    validate_date,
    validate_work,
)

console = Console()

DAY_START = minutes("00:00")
DAY_END = minutes("23:30")
LUNCH = (minutes("12:00"), minutes("13:00"))

AUTO_SLOT_CSV_INSTRUCTION = (
    "\n  Required columns: date, workHour, work (optional: startTime; other columns are ignored)"
    "\n  date: YYYY-MM-DD"
    "\n  workHour: hours as a number, multiple of 0.5 (e.g. 2, 2.5)"
    "\n  startTime (optional): minimum start time, HH:MM/HHMM/H/H.mm - blank to skip"
    "\n  Example:"
    "\n    date,workHour,work,startTime"
    "\n    2026-07-04,3,Grading Assignment 1,\n"
)


def _fmt(t: int) -> str:
    """Minutes-since-midnight to 'HH:MM'."""
    return f"{t // 60:02d}:{t % 60:02d}"


def fetch_all_course_works() -> list[dict]:
    """Fetch work entries across every course TAd in the active academic term.
    Output: (list[dict]) work dicts (date/time), pooled from all courses.
    """
    reg_year, reg_term = current_reg_time()
    courses = list_courses(reg_year, reg_term)
    works = []
    for c in courses:
        works.extend(fetch_works(c["courseId"]))
    return works


def find_free_slots(
    date_str: str,
    duration_hours: float,
    timetable: list[dict],
    all_works: list[dict],
    extra_busy: list[tuple[int, int]] = (),
) -> list[str]:
    """Enumerate free start times for a duration on a date (30-min grid, 00:00-23:30).
    Input: date_str (str) - YYYY-MM-DD, duration_hours (float), timetable (list[dict]),
        all_works (list[dict]) - work entries across courses, extra_busy (list[tuple]) -
        extra minute ranges to also treat as busy (e.g. already-placed rows in this run).
    Output: (list[str]) free 'HH:MM' start candidates, ascending.
    """
    weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()

    busy = [LUNCH]
    busy.extend((minutes(e["start"]), minutes(e["end"])) for e in entries_for_weekday(timetable, weekday))
    for w in all_works:
        if format_date(w["date"]) != date_str:
            continue
        start, end = w["time"].split("-")
        busy.append((int(start[:2]) * 60 + int(start[2:]), int(end[:2]) * 60 + int(end[2:])))
    busy.extend(extra_busy)

    duration_min = round(duration_hours * 60)
    candidates = []
    t = DAY_START
    while t + duration_min <= DAY_END:
        end_t = t + duration_min
        if not any(t < b_end and end_t > b_start for b_start, b_end in busy):
            candidates.append(_fmt(t))
        t += 30
    return candidates


def default_pick(candidates: list[str]) -> str | None:
    """Pick the highlighted default among free candidates: 8:00, else 13:00, else earliest.
    Input: candidates (list[str]) - ascending 'HH:MM' free start times.
    Output: (str | None) default candidate, or None if candidates is empty.
    """
    if "08:00" in candidates:
        return "08:00"
    if "13:00" in candidates:
        return "13:00"
    return candidates[0] if candidates else None


def _validate_duration(text: str) -> bool | str:
    """Check work-hour input is a number >=1, multiple of 0.5, for questionary.
    Input: text (str) - raw input.
    Output: (bool | str) True, or an error message.
    """
    try:
        value = float(text)
    except ValueError:
        return "Enter a number of hours (e.g. 2 or 2.5)"
    if value < 1:
        return "Must be at least 1 hour"
    if round(value * 2) != value * 2:
        return "Must be a multiple of 0.5 hours"
    return True


def _filter_by_min_start(candidates: list[str], min_start: str | None) -> list[str]:
    """Filter candidates to >= min_start, falling back to the full list if that empties it.
    Input: candidates (list[str]), min_start (str | None) - parsed 'HH:MM' or None.
    Output: (list[str]) filtered (or original) candidates.
    """
    if not min_start:
        return candidates
    filtered = [c for c in candidates if minutes(c) >= minutes(min_start)]
    if not filtered:
        console.print(f"[yellow]No free slot at/after {min_start} - showing all free slots instead.[/yellow]")
        return candidates
    return filtered


def auto_find_slot(course_id: int) -> None:
    """Single-entry Auto Find Slot flow: timetable gate, prompt, pick, confirm, submit.
    Input: course_id (int).
    """
    timetable = timetable_gate()

    date_str = questionary.text(
        "Auto Find Slot - Enter Date (YYYY-MM-DD):",
        default=datetime.now().strftime("%Y-%m-%d"),
        validate=validate_date,
        erase_when_done=True,
    ).ask()
    if date_str is None:
        raise UserCancelled

    duration_text = questionary.text(
        "Auto Find Slot - Work Hours (e.g. 2 or 2.5):",
        instruction=f"\n  Date: {date_str}\n",
        validate=_validate_duration,
        erase_when_done=True,
    ).ask()
    if duration_text is None:
        raise UserCancelled
    duration = float(duration_text)

    work = questionary.text(
        "Auto Find Slot - Enter Task:",
        instruction=f"\n  Date: {date_str}\n  Hours: {duration:g}\n",
        validate=validate_work,
        erase_when_done=True,
    ).ask()
    if work is None:
        raise UserCancelled

    all_works = fetch_all_course_works()
    candidates = find_free_slots(date_str, duration, timetable, all_works)
    if not candidates:
        console.print(f"[red]No free {duration:g}-hour slot on {date_str}.[/red]")
        return

    min_start_text = questionary.text(
        "Auto Find Slot - Minimum start time (blank to skip):",
        instruction=f"\n  Date: {date_str}\n  Hours: {duration:g}\n  Task: {work}\n",
        erase_when_done=True,
    ).ask()
    if min_start_text is None:
        raise UserCancelled
    min_start = parse_time(min_start_text) if min_start_text.strip() else None
    if min_start_text.strip() and min_start is None:
        console.print("[yellow]Could not parse minimum start time - ignoring it.[/yellow]")
    candidates = _filter_by_min_start(candidates, min_start)

    choices = [
        questionary.Choice(f"{c} - {_fmt(minutes(c) + round(duration * 60))} ({duration:g} hrs)", value=c)
        for c in candidates
    ]
    time_start = questionary.select(
        "Auto Find Slot - Choose start time:",
        choices=choices,
        default=default_pick(candidates),
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n",
        erase_when_done=True,
    ).ask()
    if time_start is None:
        raise UserCancelled
    time_end = _fmt(minutes(time_start) + round(duration * 60))

    entry = {"date": date_str, "work": work, "time_start": time_start, "time_end": time_end, "hours": duration}

    confirmed = questionary.confirm(
        "Submit this work? (Y/n)", instruction=summarize_entry(entry), erase_when_done=True
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


def _validate_bulk_row(row: dict, line: int) -> dict | None:
    """Validate one bulk-auto-find-slot CSV row.
    Input: row (dict), line (int) - 1-indexed CSV line number (for error messages).
    Output: (dict | None) {date, duration, work, min_start}, or None if blank/invalid.
    """
    if not any((row.get(col) or "").strip() for col in ("date", "workHour", "work")):
        return None

    errors = []

    if validate_date(row["date"]) is not True:
        errors.append(f"date {validate_date(row['date'])}")

    duration_ok = _validate_duration(row.get("workHour", ""))
    if duration_ok is not True:
        errors.append(f"workHour {duration_ok}")

    if validate_work(row["work"]) is not True:
        errors.append(validate_work(row["work"]))

    min_start = None
    start_text = (row.get("startTime") or "").strip()
    if start_text:
        min_start = parse_time(start_text)
        if min_start is None:
            errors.append("startTime invalid format")

    if errors:
        console.print(f"[red]Row {line}: {'; '.join(errors)}[/red]")
        return None

    return {"date": row["date"], "duration": float(row["workHour"]), "work": row["work"], "min_start": min_start}


def auto_find_slot_bulk(course_id: int) -> None:
    """Bulk Auto Find Slot flow: timetable gate, CSV, auto-pick each row, confirm, submit all.
    Input: course_id (int).
    """
    timetable = timetable_gate()

    path = select_csv_path(
        title="Auto Find Slot (bulk) - CSV file:", instruction=AUTO_SLOT_CSV_INSTRUCTION
    )
    if path is None:
        return

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [c for c in ("date", "workHour", "work") if c not in (reader.fieldnames or [])]
            if missing:
                console.print(f"[red]CSV missing columns: {', '.join(missing)}[/red]")
                return
            rows = list(reader)
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
        return
    if not rows:
        return

    all_works = fetch_all_course_works()
    extra_busy: dict[str, list[tuple[int, int]]] = {}
    entries = []
    for i, row in enumerate(rows, start=2):
        parsed = _validate_bulk_row(row, i)
        if parsed is None:
            continue

        candidates = find_free_slots(
            parsed["date"], parsed["duration"], timetable, all_works, extra_busy.get(parsed["date"], [])
        )
        candidates = _filter_by_min_start(candidates, parsed["min_start"])
        if not candidates:
            console.print(f"[red]Row {i}: no free {parsed['duration']:g}-hour slot on {parsed['date']}.[/red]")
            continue

        time_start = default_pick(candidates)
        time_end = _fmt(minutes(time_start) + round(parsed["duration"] * 60))
        extra_busy.setdefault(parsed["date"], []).append((minutes(time_start), minutes(time_end)))
        entries.append(
            {
                "date": parsed["date"],
                "work": parsed["work"],
                "time_start": time_start,
                "time_end": time_end,
                "hours": parsed["duration"],
            }
        )

    if not entries:
        console.print("[yellow]No valid rows to submit.[/yellow]")
        return

    console.print("\n[bold]Summary[/bold]")
    for e in entries:
        console.print(f"{e['date']} | {e['time_start']} - {e['time_end']} ({e['hours']:g} hrs) | {e['work']}")
    total_hours = sum(e["hours"] for e in entries)
    console.print(f"\n[bold]Total: {total_hours:g} hrs across {len(entries)} work(s)[/bold]\n")

    confirmed = questionary.confirm(f"Submit {len(entries)} valid work(s)?").ask()
    if confirmed is None:
        raise UserCancelled
    if not confirmed:
        return

    for entry in entries:
        submit_work(course_id, entry)
        console.print(
            f"[bold green]Added:[/bold green] {entry['date']} | {entry['time_start']} - "
            f"{entry['time_end']} | {entry['work']}"
        )


def _demo() -> None:
    """Self-check: slot enumeration/overlap and default-pick priority (no network)."""
    timetable = [{"name": "Course", "weekday": 1, "start": "09:00", "end": "10:30"}]
    works = [{"date": "2026-08-04T00:00:00.000Z", "time": "1000-1200"}]

    candidates = find_free_slots("2026-08-04", 2, timetable, works)
    assert "07:00" in candidates
    assert "08:00" not in candidates  # overlaps the 09:00-10:30 timetable entry
    assert "10:00" not in candidates  # overlaps the 10:00-12:00 work entry
    assert "12:00" not in candidates  # overlaps lunch
    assert default_pick(candidates) == "13:00"  # 08:00 busy, so falls to 13:00

    assert default_pick([]) is None

    lunch_check = find_free_slots("2026-08-04", 1, [], [])
    assert "11:00" in lunch_check
    assert "12:00" not in lunch_check
    assert "13:00" in lunch_check


if __name__ == "__main__":
    _demo()
    print("OK")

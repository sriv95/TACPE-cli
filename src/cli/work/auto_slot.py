"""Auto Find Slot: find TA-work start times free of lunch, timetable, and existing works."""

from datetime import datetime

import questionary
from rich.console import Console

from src.cli.work.bulk_works import read_csv_rows, select_csv_path
from src.cli.course import current_reg_time, list_courses
from src.helper.batch import run_batch
from src.helper.prompt import ask, confirm_or_cancel
from src.cli.work.timetable import entries_for_weekday, timetable_gate
from src.cli.work.works import (
    fetch_works,
    format_date,
    format_entry_line,
    minutes,
    parse_date,
    parse_time,
    split_time,
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
    "\n  Required columns: date, workHour, work (or task; optional: startTime; other columns are ignored)"
    "\n  date: YYYY-MM-DD"
    "\n  workHour: hours as a number (e.g. 2, 2.5) or HH:mm[:ss] (e.g. 1:30, 1:30:00), multiple of 0.5"
    "\n  startTime (optional): earliest start time, HH:MM/HHMM/H/H.mm - odd minutes round up to next 00/30 - slot placed at next free time at/after it - blank to skip"
    "\n  Example:"
    "\n    date,workHour,work,startTime"
    "\n    2026-07-04,3,Grading Assignment 1,\n"
)


def _fmt(t: int) -> str:
    """Minutes-since-midnight to 'HH:MM'.
    Input: t (int) - minutes since midnight.
    Output: (str) 'HH:MM'.
    """
    return f"{t // 60:02d}:{t % 60:02d}"


def fetch_all_course_works(reg_year: int | None = None, reg_term: int | None = None) -> list[dict]:
    """Fetch work entries across every course TAd in a term.
    Input: reg_year (int | None), reg_term (int | None) - term to pool from, default: the active term.
    Output: (list[dict]) work dicts (date/time), pooled from all courses.
    """
    if reg_year is None:
        reg_year, reg_term = current_reg_time()
    courses = list_courses(reg_year, reg_term)
    works = []
    for c in courses:
        works.extend(fetch_works(c["courseId"]))
    return works


def find_overlap_conflicts(courses: list[dict], timetable: list[dict]) -> list[str]:
    """Find overlapping work entries across courses (lunch/timetable/each other), via entry_overlap_reasons.
    Input: courses (list[dict]) - TA/course dicts, timetable (list[dict]).
    Output: (list[str]) human-readable conflict descriptions.
    """
    works = []
    for c in courses:
        label = f"{c['course']['courseTemplate']['courseNo']} | Sec:{c['course']['section']:03d}"
        works.extend({**w, "_label": label} for w in fetch_works(c["courseId"]))

    def labeled(w: dict) -> str:
        return f"[{w['_label']}] {w['work']}"

    conflicts = []
    for i, w in enumerate(works):
        date_str = format_date(w["date"])
        start, end = split_time(w["time"])
        reasons = entry_overlap_reasons(date_str, start, end, timetable, works[i + 1 :], work_label=labeled)
        conflicts.extend(f"{date_str}: {labeled(w)} ({start}-{end}) overlaps {r}" for r in reasons)
    return conflicts


def print_overlap_conflicts(conflicts: list[str]) -> None:
    """Print overlap conflicts (or a none-found message), rich-formatted.
    Input: conflicts (list[str]).
    """
    console.print()
    if conflicts:
        console.print(f"[bold red]Found {len(conflicts)} overlap(s):[/bold red]")
        for c in conflicts:
            console.print(f"  [yellow]{c}[/yellow]")
    else:
        console.print("[bold green]No overlaps found.[/bold green]")
    console.print()


def check_overlap_all_courses(reg_year: int, reg_term: int) -> None:
    """Timetable gate, then report overlapping work entries across every course in a term.
    Input: reg_year (int), reg_term (int).
    """
    timetable = timetable_gate(proceed_label="Check")
    courses = list_courses(reg_year, reg_term)
    print_overlap_conflicts(find_overlap_conflicts(courses, timetable))


def _default_work_label(w: dict) -> str:
    return f"existing work: {w['work']}"


def _busy_ranges(
    date_str: str,
    timetable: list[dict],
    all_works: list[dict],
    extra_busy: list[tuple[int, int, str]] = (),
    work_label=_default_work_label,
) -> list[tuple[int, int, str]]:
    """Build the list of busy minute ranges (lunch + timetable + existing works + extras) for a date.
    Input: date_str (str) - YYYY-MM-DD, timetable (list[dict]), all_works (list[dict]),
        extra_busy (list[tuple[int, int, str]]) - extra (start_min, end_min, label) ranges,
        work_label (callable) - builds a work's busy-range label from its dict.
    Output: (list[tuple[int, int, str]]) (start_min, end_min, label) ranges.
    """
    weekday = datetime.strptime(date_str, "%Y-%m-%d").weekday()

    busy = [(*LUNCH, "lunch break")]
    busy.extend(
        (minutes(e["start"]), minutes(e["end"]), f"timetable: {e['name']}")
        for e in entries_for_weekday(timetable, weekday)
    )
    for w in all_works:
        if format_date(w["date"]) != date_str:
            continue
        start, end = split_time(w["time"])
        busy.append((minutes(start), minutes(end), work_label(w)))
    busy.extend(extra_busy)
    return busy


def entry_overlap_reasons(
    date_str: str,
    time_start: str,
    time_end: str,
    timetable: list[dict],
    all_works: list[dict],
    extra_busy: list[tuple[int, int, str]] = (),
    work_label=_default_work_label,
) -> list[str]:
    """Find overlap reasons (lunch/timetable/other works/extras) for an explicit time range on a date.
    Input: date_str (str) - YYYY-MM-DD, time_start/time_end (str) - 'HH:MM', timetable (list[dict]),
        all_works (list[dict]) - work entries across courses, extra_busy (list[tuple[int, int, str]]) -
        extra (start_min, end_min, label) ranges to also treat as busy, work_label (callable) -
        builds a work's busy-range label from its dict.
    Output: (list[str]) overlap reasons, [] if none.
    """
    busy = _busy_ranges(date_str, timetable, all_works, extra_busy, work_label)
    start_min, end_min = minutes(time_start), minutes(time_end)
    return [
        f"{label} ({_fmt(b_start)}-{_fmt(b_end)})"
        for b_start, b_end, label in busy
        if start_min < b_end and end_min > b_start
    ]


def slots_with_overlap(
    date_str: str,
    duration_hours: float,
    timetable: list[dict],
    all_works: list[dict],
    extra_busy: list[tuple[int, int, str]] = (),
) -> list[tuple[str, list[str]]]:
    """Enumerate every start-time candidate for a duration on a date (30-min grid, 00:00-23:30),
    each with the reasons (if any) it overlaps lunch/timetable/existing works.
    Input: date_str (str) - YYYY-MM-DD, duration_hours (float), timetable (list[dict]),
        all_works (list[dict]) - work entries across courses, extra_busy (list[tuple[int, int, str]]) -
        extra (start_min, end_min, label) ranges to also treat as busy (e.g. already-placed rows in this run).
    Output: (list[tuple[str, list[str]]]) (start 'HH:MM', overlap reasons - empty if free), ascending.
    """
    busy = _busy_ranges(date_str, timetable, all_works, extra_busy)

    duration_min = round(duration_hours * 60)
    slots = []
    t = DAY_START
    while t + duration_min <= DAY_END:
        end_t = t + duration_min
        reasons = [
            f"{label} ({_fmt(b_start)}-{_fmt(b_end)})"
            for b_start, b_end, label in busy
            if t < b_end and end_t > b_start
        ]
        slots.append((_fmt(t), reasons))
        t += 30
    return slots


def find_free_slots(
    date_str: str,
    duration_hours: float,
    timetable: list[dict],
    all_works: list[dict],
    extra_busy: list[tuple[int, int, str]] = (),
) -> list[str]:
    """Enumerate free (non-overlapping) start times for a duration on a date.
    Input: same as slots_with_overlap.
    Output: (list[str]) free 'HH:MM' start candidates, ascending.
    """
    return [t for t, reasons in slots_with_overlap(date_str, duration_hours, timetable, all_works, extra_busy) if not reasons]


def default_pick(candidates: list[str], prefer_earliest: bool = False) -> str | None:
    """Pick the highlighted default among free candidates.
    Input: candidates (list[str]) - ascending 'HH:MM' free start times,
        prefer_earliest (bool) - when a min start time was given, pick the first free
        slot at/after it (i.e. candidates[0]) instead of the 08:00/13:00/latest default.
    Output: (str | None) default candidate, or None if candidates is empty.
    """
    if not candidates:
        return None
    if prefer_earliest:
        return candidates[0]
    if "08:00" in candidates:
        return "08:00"
    if "13:00" in candidates:
        return "13:00"
    return candidates[-1] if candidates else None


def parse_work_hours(text: str) -> float | None:
    """Parse work-hours input: a number (2, 2.5) or HH:mm[:ss] (1:30, 1:30:00).
    Input: text (str) - raw input.
    Output: (float | None) hours, or None if unparseable.
    """
    text = text.strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
            return None
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) == 3 else 0
        return h + m / 60 + s / 3600
    try:
        return float(text)
    except ValueError:
        return None


def _validate_duration(text: str) -> bool | str:
    """Check work-hour input is >=1 hour, multiple of 0.5, for questionary.
    Input: text (str) - raw input (number or HH:mm[:ss]).
    Output: (bool | str) True, or an error message.
    """
    value = parse_work_hours(text)
    if value is None:
        return "Enter hours (e.g. 2, 2.5) or HH:mm[:ss] (e.g. 1:30)"
    if value < 1:
        return "Must be at least 1 hour"
    if round(value * 2) != value * 2:
        return "Must be a multiple of 0.5 hours"
    return True


def _filter_by_min_start(items: list, min_start: str | None, key=lambda item: item, desc: str = "free slot") -> list:
    """Filter items to key(item) >= min_start, falling back to the full list if that empties it.
    Input: items (list), min_start (str | None) - parsed 'HH:MM' or None, key (callable) - extracts
        'HH:MM' from an item, desc (str) - noun used in the fallback message.
    Output: (list) filtered (or original) items.
    """
    if not min_start:
        return items
    filtered = [i for i in items if minutes(key(i)) >= minutes(min_start)]
    if not filtered:
        console.print(f"[yellow]No {desc} at/after {min_start} - showing all {desc}s instead.[/yellow]")
        return items
    return filtered


def auto_find_slot(course_id: int) -> None:
    """Single-entry Auto Find Slot flow: timetable gate, prompt, pick, confirm, submit.
    Input: course_id (int).
    """
    timetable = timetable_gate()

    date_str = parse_date(ask(questionary.text(
        "Auto Find Slot - Enter Date (YYYY-MM-DD or DDMonYYYY):",
        default=datetime.now().strftime("%Y-%m-%d"),
        validate=validate_date,
        erase_when_done=True,
    )))

    duration_text = ask(questionary.text(
        "Auto Find Slot - Work Hours (e.g. 2, 2.5 or 1:30):",
        instruction=f"\n  Date: {date_str}\n",
        validate=_validate_duration,
        erase_when_done=True,
    ))
    duration = parse_work_hours(duration_text)

    work = ask(questionary.text(
        "Auto Find Slot - Enter Task:",
        instruction=f"\n  Date: {date_str}\n  Hours: {duration:g}\n",
        validate=validate_work,
        erase_when_done=True,
    ))

    all_works = fetch_all_course_works()
    all_slots = slots_with_overlap(date_str, duration, timetable, all_works)
    if not all_slots:
        console.print(f"[red]No {duration:g}-hour slot fits in the day.[/red]")
        return

    min_start_text = ask(questionary.text(
        "Auto Find Slot - Earliest start time (blank to skip):",
        instruction=f"\n  Date: {date_str}\n  Hours: {duration:g}\n  Task: {work}\n",
        erase_when_done=True,
    ))
    min_start = parse_time(min_start_text, round_up=True) if min_start_text.strip() else None
    if min_start_text.strip() and min_start is None:
        console.print("[yellow]Could not parse minimum start time - ignoring it.[/yellow]")
    all_slots = _filter_by_min_start(all_slots, min_start, key=lambda s: s[0], desc="slot")

    free_times = [t for t, reasons in all_slots if not reasons]
    default = default_pick(free_times, prefer_earliest=bool(min_start)) or all_slots[0][0]

    choices = [
        questionary.Choice(
            f"{c} - {_fmt(minutes(c) + round(duration * 60))} ({duration:g} hrs)"
            + (f"  [!] overlaps {', '.join(reasons)}" if reasons else ""),
            value=c,
        )
        for c, reasons in all_slots
    ]
    time_start = ask(questionary.select(
        "Auto Find Slot - Choose start time:",
        choices=choices,
        default=default,
        instruction=f"\n  Date: {date_str}\n  Task: {work}\n",
        erase_when_done=True,
    ))
    time_end = _fmt(minutes(time_start) + round(duration * 60))

    entry = {"date": date_str, "work": work, "time_start": time_start, "time_end": time_end, "hours": duration}

    chosen_reasons = next((reasons for c, reasons in all_slots if c == time_start), [])
    if chosen_reasons:
        console.print(f"[yellow]Warning: chosen time overlaps {', '.join(chosen_reasons)}.[/yellow]")

    if not confirm_or_cancel("Submit this work? (Y/n)", instruction=summarize_entry(entry), erase_when_done=True):
        return

    submit_work(course_id, entry)
    console.print(f"[bold green]Added:[/bold green] {format_entry_line(entry)}")


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
        min_start = parse_time(start_text, round_up=True)
        if min_start is None:
            errors.append("startTime invalid format")

    if errors:
        console.print(f"[red]Row {line}: {'; '.join(errors)}[/red]")
        return None

    return {
        "date": parse_date(row["date"]),
        "duration": parse_work_hours(row["workHour"]),
        "work": row["work"],
        "min_start": min_start,
    }


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
        rows = read_csv_rows(path, ("date", "workHour", "work"))
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
        return
    if not rows:
        return

    all_works = fetch_all_course_works()
    extra_busy: dict[str, list[tuple[int, int, str]]] = {}
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

        time_start = default_pick(candidates, prefer_earliest=bool(parsed["min_start"]))
        time_end = _fmt(minutes(time_start) + round(parsed["duration"] * 60))
        extra_busy.setdefault(parsed["date"], []).append(
            (minutes(time_start), minutes(time_end), "another row in this run")
        )
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
        console.print(format_entry_line(e))
    total_hours = sum(e["hours"] for e in entries)
    console.print(f"\n[bold]Total: {total_hours:g} hrs across {len(entries)} work(s)[/bold]\n")

    if not confirm_or_cancel(f"Submit {len(entries)} valid work(s)?"):
        return

    added, failed = run_batch(
        entries,
        lambda e: submit_work(course_id, e),
        lambda e: e["date"],
        "add",
        lambda e: console.print(f"[bold green]Added:[/bold green] {format_entry_line(e)}"),
    )
    console.print(f"[bold green]Added {added} work(s).[/bold green]" + (f" [red]{failed} failed.[/red]" if failed else ""))


def _demo() -> None:
    """Self-check: slot enumeration/overlap and default-pick priority (no network)."""
    timetable = [{"name": "Course", "weekday": 1, "start": "09:00", "end": "10:30"}]
    works = [{"date": "2026-08-04T00:00:00.000Z", "time": "1000-1200", "work": "Grading"}]

    slots = slots_with_overlap("2026-08-04", 2, timetable, works)
    reasons = dict(slots)
    assert reasons["08:00"] == ["timetable: Course (09:00-10:30)"]
    assert reasons["10:00"] == ["timetable: Course (09:00-10:30)", "existing work: Grading (10:00-12:00)"]
    assert reasons["12:00"] == ["lunch break (12:00-13:00)"]

    candidates = find_free_slots("2026-08-04", 2, timetable, works)
    assert "07:00" in candidates
    assert "08:00" not in candidates  # overlaps the 09:00-10:30 timetable entry
    assert "10:00" not in candidates  # overlaps the 10:00-12:00 work entry
    assert "12:00" not in candidates  # overlaps lunch
    assert default_pick(candidates) == "13:00"  # 08:00 busy, so falls to 13:00

    assert default_pick([]) is None
    assert default_pick(["00:00", "00:30", "05:00"]) == "05:00"  # neither 08:00 nor 13:00 free, falls to latest

    # prefer_earliest: with a min start time given, take the first free slot, not 08:00/13:00
    open_day = find_free_slots("2026-08-04", 1, [], [])
    after_nine = _filter_by_min_start(open_day, "09:00")
    assert default_pick(after_nine) == "13:00"  # old behavior jumps to 13:00
    assert default_pick(after_nine, prefer_earliest=True) == "09:00"  # next free slot from 09:00
    assert default_pick([], prefer_earliest=True) is None

    lunch_check = find_free_slots("2026-08-04", 1, [], [])
    assert "11:00" in lunch_check
    assert "12:00" not in lunch_check
    assert "13:00" in lunch_check


if __name__ == "__main__":
    _demo()
    print("OK")

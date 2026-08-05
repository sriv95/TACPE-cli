"""Recurring weekly enrolled-course timetable, used by Auto Find Slot to avoid clashes."""

import json
from pathlib import Path

import questionary
from rich.console import Console

from src.helper.prompt import ask
from src.cli.work.works import minutes, parse_time

console = Console()

TIMETABLE_FILE = Path(__file__).resolve().parent.parent / ".cache" / ".timetable"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

BACK = object()
ADD_TIME = object()


def load_timetable() -> list[dict]:
    """Read the saved timetable, if any.
    Output: (list[dict]) entries with name/weekday/start/end, [] if no file.
    """
    if not TIMETABLE_FILE.exists():
        return []
    return json.loads(TIMETABLE_FILE.read_text())


def save_timetable(entries: list[dict]) -> None:
    """Persist the timetable to disk.
    Input: entries (list[dict]).
    """
    TIMETABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TIMETABLE_FILE.write_text(json.dumps(entries, indent=2))


def entries_for_weekday(entries: list[dict], weekday: int) -> list[dict]:
    """Filter timetable entries to a given weekday.
    Input: entries (list[dict]), weekday (int) - 0=Mon..6=Sun.
    Output: (list[dict]) matching entries.
    """
    return [e for e in entries if e["weekday"] == weekday]


def _validate_weekday_time(text: str) -> bool | str:
    return True if parse_time(text, strict=False) else "Format: HH:MM (any minute)"


def _prompt_time_entry(defaults: dict | None = None) -> dict | None:
    """Prompt Name/weekday/startTime/endTime, prefilled from defaults.
    Input: defaults (dict | None) - prefill name/weekday/start/end.
    Output: (dict | None) entry, or None if cancelled.
    """
    defaults = defaults or {}
    name = ask(questionary.text(
        "Timetable - Name (course):", default=defaults.get("name", ""), erase_when_done=True
    ))

    weekday = ask(questionary.select(
        "Timetable - Day of week:",
        choices=[questionary.Choice(day, value=i) for i, day in enumerate(WEEKDAYS)],
        default=defaults.get("weekday"),
        erase_when_done=True,
    ))

    start = ask(questionary.text(
        "Timetable - Start Time (HH:MM):",
        default=defaults.get("start", ""),
        validate=_validate_weekday_time,
        erase_when_done=True,
    ))
    start = parse_time(start, strict=False)

    end = ask(questionary.text(
        "Timetable - End Time (HH:MM):",
        default=defaults.get("end", ""),
        validate=lambda t: _validate_weekday_time(t)
        if parse_time(t, strict=False) is None or minutes(parse_time(t, strict=False)) > minutes(start)
        else "End time must be after start time",
        erase_when_done=True,
    ))
    end = parse_time(end, strict=False)

    return {"name": name, "weekday": weekday, "start": start, "end": end}


def _row_label(entry: dict) -> str:
    return f"{WEEKDAYS[entry['weekday']]} | {entry['start']} - {entry['end']} | {entry['name']}"


def edit_timetable_menu() -> None:
    """List timetable entries as choices, with Add Time / Back."""
    while True:
        entries = load_timetable()
        choices = [questionary.Choice(_row_label(e), value=i) for i, e in enumerate(entries)]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("Add Time", value=ADD_TIME))
        choices.append(questionary.Choice("Back to Time Table", value=BACK))

        selected = ask(questionary.select("Edit Time Table:", choices=choices, erase_when_done=True))
        if selected is BACK:
            return
        if selected is ADD_TIME:
            entry = _prompt_time_entry()
            entries.append(entry)
            save_timetable(entries)
            continue

        entry = _prompt_time_entry(defaults=entries[selected])
        entries[selected] = entry
        save_timetable(entries)


def timetable_gate(proceed_label: str = "Next") -> list[dict]:
    """Show current timetable and offer proceed/Edit before an Auto Find Slot or overlap-check run.
    Input: proceed_label (str) - text for the proceed choice.
    Output: (list[dict]) the timetable to use (re-read after any edits).
    """
    while True:
        entries = load_timetable()
        if entries:
            instruction = "\n  Enrolled Course Time Table:\n" + "\n".join(
                f"    {_row_label(e)}" for e in entries
            ) + "\n"
        else:
            instruction = "\n  No timetable entries yet.\n"

        choice = ask(questionary.select(
            "Time Table:",
            choices=[
                questionary.Choice(proceed_label, value="next"),
                questionary.Choice("Edit Time Table", value="edit"),
            ],
            instruction=instruction,
            erase_when_done=True,
        ))
        if choice == "edit":
            edit_timetable_menu()
            continue

        return load_timetable()


def _demo() -> None:
    """Self-check: weekday filtering (no network)."""
    entries = [
        {"name": "A", "weekday": 0, "start": "09:00", "end": "10:15"},
        {"name": "B", "weekday": 2, "start": "14:00", "end": "15:00"},
    ]
    assert entries_for_weekday(entries, 0) == [entries[0]]
    assert entries_for_weekday(entries, 1) == []


if __name__ == "__main__":
    _demo()
    print("OK")

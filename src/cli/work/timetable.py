"""Recurring weekly enrolled-course timetable, used by Auto Find Slot to avoid clashes."""

import json

import questionary
from rich.console import Console

from src.helper.prompt import ask
from src.cli.work.works import minutes, parse_time
from src.func.const import CONFIG_DIR

console = Console()

TIMETABLE_FILE = CONFIG_DIR / ".timetable"

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


def _prompt_time_entry(defaults: dict | None = None) -> list[dict] | None:
    """Prompt Name/weekdays/startTime/endTime, prefilled from defaults.
    Input: defaults (dict | None) - prefill name/weekday/start/end.
    Output: (list[dict] | None) one entry per chosen weekday, or None if cancelled.
    """
    defaults = defaults or {}
    name = ask(questionary.text(
        "Timetable - Name (course):", default=defaults.get("name", ""), erase_when_done=True
    ))

    checked = set(defaults.get("weekdays", []))
    if "weekday" in defaults:
        checked.add(defaults["weekday"])
    weekdays = ask(questionary.checkbox(
        "Timetable - Days of week:",
        choices=[
            questionary.Choice(day, value=i, checked=i in checked)
            for i, day in enumerate(WEEKDAYS)
        ],
        validate=lambda picked: bool(picked) or "Pick at least one day",
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

    return [
        {"name": name, "weekday": wd, "start": start, "end": end}
        for wd in sorted(weekdays)
    ]


def _row_label(entry: dict) -> str:
    return f"{WEEKDAYS[entry['weekday']]} | {entry['start']} - {entry['end']} | {entry['name']}"


def _group_entries(entries: list[dict]) -> list[dict]:
    """Group entries sharing name+start+end into one row spanning multiple weekdays.
    Input: entries (list[dict]).
    Output: (list[dict]) groups with name/start/end/weekdays/indices, weekdays+indices sorted by weekday.
    """
    groups: list[dict] = []
    by_key: dict[tuple, dict] = {}
    for i, e in enumerate(entries):
        key = (e["name"], e["start"], e["end"])
        g = by_key.get(key)
        if g is None:
            g = {"name": e["name"], "start": e["start"], "end": e["end"], "weekdays": [], "indices": []}
            by_key[key] = g
            groups.append(g)
        g["weekdays"].append(e["weekday"])
        g["indices"].append(i)
    for g in groups:
        order = sorted(range(len(g["weekdays"])), key=lambda k, g=g: g["weekdays"][k])
        g["weekdays"] = [g["weekdays"][k] for k in order]
        g["indices"] = [g["indices"][k] for k in order]
    return groups


def _group_label(group: dict) -> str:
    days = ",".join(WEEKDAYS[w] for w in group["weekdays"])
    return f"{days} | {group['start']} - {group['end']} | {group['name']}"


def edit_timetable_menu() -> None:
    """List timetable entries as choices, with Add Time / Back."""
    while True:
        entries = load_timetable()
        groups = _group_entries(entries)
        choices = [questionary.Choice(_group_label(g), value=gi) for gi, g in enumerate(groups)]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("Add Time", value=ADD_TIME))
        choices.append(questionary.Choice("Back to Time Table", value=BACK))

        selected = ask(questionary.select("Edit Time Table:", choices=choices, erase_when_done=True))
        if selected is BACK:
            return
        if selected is ADD_TIME:
            entries.extend(_prompt_time_entry())
            save_timetable(entries)
            continue

        group = groups[selected]
        action = ask(questionary.select(
            _group_label(group),
            choices=[
                questionary.Choice("Edit", value="edit"),
                questionary.Choice("Delete", value="delete"),
                questionary.Choice("Back", value=BACK),
            ],
            erase_when_done=True,
        ))
        if action is BACK:
            continue
        if action == "delete":
            for i in sorted(group["indices"], reverse=True):
                del entries[i]
            save_timetable(entries)
            continue

        new = _prompt_time_entry(defaults={
            "name": group["name"], "start": group["start"],
            "end": group["end"], "weekdays": group["weekdays"],
        })
        at = min(group["indices"])
        for i in sorted(group["indices"], reverse=True):
            del entries[i]
        entries[at:at] = new
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
                f"    {_group_label(g)}" for g in _group_entries(entries)
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

    base = [{"name": "C", "weekday": w, "start": "09:00", "end": "10:00"} for w in (4, 0, 2)]
    lst = [entries[0], entries[1]]
    lst[0:1] = base
    assert [e["weekday"] for e in lst] == [4, 0, 2, 2]

    groups = _group_entries(lst)
    assert [g["name"] for g in groups] == ["C", "B"]
    assert groups[0]["weekdays"] == [0, 2, 4]
    assert groups[0]["indices"] == [1, 2, 0]
    assert _group_label(groups[0]) == "Mon,Wed,Fri | 09:00 - 10:00 | C"

    for i in sorted(groups[0]["indices"], reverse=True):
        del lst[i]
    assert [e["weekday"] for e in lst] == [2]


if __name__ == "__main__":
    _demo()
    print("OK")

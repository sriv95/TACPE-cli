"""Recurring weekly enrolled-course timetable, used by Auto Find Slot to avoid clashes."""

import csv
import json
from pathlib import Path

import questionary
from rich.console import Console

from src.helper.prompt import ask
from src.cli.work.bulk_works import read_csv_rows, select_csv_path
from src.cli.work.works import minutes, parse_time
from src.func.const import CONFIG_DIR

console = Console()

TIMETABLE_FILE = CONFIG_DIR / ".timetable"

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

COLUMNS = ("name", "day", "startTime", "endTime")

BACK = object()
ADD_TIME = object()
IMPORT = object()
EXPORT = object()


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


def export_timetable(entries: list[dict], path: str) -> None:
    """Write the timetable to a CSV file (columns name/day/startTime/endTime).
    Input: entries (list[dict]), path (str).
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for e in entries:
            writer.writerow([e["name"], WEEKDAYS[e["weekday"]], e["start"], e["end"]])


def parse_timetable_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate CSV rows into timetable entries.
    Input: rows (list[dict]) - dicts with name/day/startTime/endTime.
    Output: (entries, errors) - valid entries, and one message per bad row (blank rows skipped).
    """
    entries, errors = [], []
    for line, row in enumerate(rows, start=2):
        if not any((row.get(c) or "").strip() for c in COLUMNS):
            continue
        name = (row["name"] or "").strip()
        day = (row["day"] or "").strip().title()[:3]
        start = parse_time(row["startTime"] or "", strict=False)
        end = parse_time(row["endTime"] or "", strict=False)
        problems = []
        if not name:
            problems.append("name empty")
        if day not in WEEKDAYS:
            problems.append("day must be Mon..Sun")
        if start is None:
            problems.append("startTime invalid format")
        if end is None:
            problems.append("endTime invalid format")
        if start and end and minutes(end) <= minutes(start):
            problems.append("endTime must be after startTime")
        if problems:
            errors.append(f"Row {line}: {'; '.join(problems)}")
            continue
        entries.append({"name": name, "weekday": WEEKDAYS.index(day), "start": start, "end": end})
    return entries, errors


def import_timetable(path: str, replace: bool = False) -> tuple[int, list[str]]:
    """Import timetable entries from CSV; saves nothing if any row is invalid.
    Input: path (str), replace (bool) - overwrite the saved timetable instead of merging (duplicates skipped).
    Output: (int, list[str]) - number of entries added, row errors.
    Raises FileNotFoundError / ValueError (missing columns) on a bad file.
    """
    rows = read_csv_rows(path, COLUMNS)
    if rows is None:
        raise ValueError("CSV missing columns")
    new, errors = parse_timetable_rows(rows)
    if errors:
        return 0, errors
    merged = [] if replace else load_timetable()
    before = len(merged)
    for e in new:
        if e not in merged:
            merged.append(e)
    save_timetable(merged)
    return len(merged) - before, []


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


def _import_flow() -> None:
    path = select_csv_path(
        "Import Time Table - CSV file:",
        "\n  Columns: name, day (Mon..Sun), startTime, endTime (one row per day)\n",
    )
    if path is None:
        return
    replace = ask(questionary.select(
        "Import mode:",
        choices=[
            questionary.Choice("Merge with current (skip duplicates)", value=False),
            questionary.Choice("Replace current", value=True),
        ],
        erase_when_done=True,
    ))
    try:
        added, errors = import_timetable(path, replace=replace)
    except FileNotFoundError:
        console.print(f"[red]File not found: {path}[/red]")
        return
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return
    for err in errors:
        console.print(f"[red]{err}[/red]")
    if errors:
        console.print("[red]Nothing imported - fix the rows above.[/red]")
    else:
        console.print(f"[bold green]Imported {added} entries.[/bold green]")


def _export_flow(entries: list[dict]) -> None:
    path = ask(questionary.text("Export Time Table - CSV path:", default="timetable.csv", erase_when_done=True))
    export_timetable(entries, str(Path(path).expanduser()))
    console.print(f"[bold green]Exported {len(entries)} entries to {path}.[/bold green]")


def edit_timetable_menu() -> None:
    """List timetable entries as choices, with Add Time / Back."""
    while True:
        entries = load_timetable()
        groups = _group_entries(entries)
        choices = [questionary.Choice(_group_label(g), value=gi) for gi, g in enumerate(groups)]
        choices.append(questionary.Separator())
        choices.append(questionary.Choice("Add Time", value=ADD_TIME))
        choices.append(questionary.Choice("Import from CSV", value=IMPORT))
        choices.append(questionary.Choice("Export to CSV", value=EXPORT))
        choices.append(questionary.Choice("Back to Time Table", value=BACK))

        selected = ask(questionary.select("Edit Time Table:", choices=choices, erase_when_done=True))
        if selected is BACK:
            return
        if selected is ADD_TIME:
            entries.extend(_prompt_time_entry())
            save_timetable(entries)
            continue
        if selected is IMPORT:
            _import_flow()
            continue
        if selected is EXPORT:
            _export_flow(entries)
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

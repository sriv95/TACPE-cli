# Multi-Date Add Work — Design

## Goal

Extend "Add a work" (single-entry add) so one task/time can be submitted to
multiple dates in one pass: every week until a chosen cutoff, or an arbitrary
multi-select of dates. "Just this date" preserves today's single-entry
behavior.

## Flow

Replaces `add_works(course_id)` in `src/works.py`. New shape:

1. **Date prompt** (`_prompt_date`, extracted from `_prompt_work_entry`) —
   text input, default = today (Bangkok), format `YYYY-MM-DD`. Range-validated
   to `[1st of last month relative to today, today]`. This becomes the
   **selected date**, the anchor for step 3.
2. **Mode select**:
   - `1. Just this date`
   - `2. Every week until date`
   - `3. Multiple dates (multi-select)`
   - `Back`
3. **Date-list resolution** (skipped for mode 1, where `dates = [selected_date]`):
   - Bound for both list modes: `[1st of last month relative to the SELECTED
     DATE, today]` — recomputed from the selected date, not today. (Different
     from step 1's bound, which is always relative to today since no selected
     date exists yet at that point.)
   - **Mode 2 (weekly)** — `questionary.select` listing only the dates that
     share the selected date's weekday, spaced 7 days apart, newest-first,
     within the bound. Cursor starts on the selected date. Each choice labeled
     with weekday abbreviation, e.g. `2026-07-20 (Mon)`; the newest and oldest
     rows additionally annotated `(today)` / `(1st of last month)` when they
     land there. Picking a row sets it as the "until" cutoff; `dates` = every
     listed date from the selected date down through the cutoff (inclusive).
   - **Mode 3 (multi-select)** — `questionary.checkbox` listing every calendar
     day in the bound, newest-first. Selected date's box starts pre-checked;
     cursor starts there. User toggles any others. `dates` = all checked
     dates. Empty selection (user unchecked everything) → no-op, return to
     the add-works menu (same pattern as `delete_multiple_works`).
4. **Task/time prompt** (`_prompt_task_time`, extracted from
   `_prompt_work_entry`) — asked once: task text, start time, end time. Same
   validation as today (`validate_work`, `_validate_time`, `_validate_time_end`).
5. **Summary + single confirm** — one row per date, same line format as the
   existing per-date result lines (`{date} | {start} - {end} ({hours} hrs) |
   {task}`), followed by hours/lunch warnings computed once (they're identical
   across dates since task/time is shared) and `Submit these N work(s)? (Y/n)`.
6. **Submit loop** — `submit_work` per date, catching per-item exceptions the
   same way `delete_multiple_works` does (report the failure, continue with
   the rest), then print one `Added: ...` line per success and a final
   `Added N work(s).` (+ `M failed.` if any).

`edit_work_entry` and `clone_work_entry` are unaffected — they keep using a
single date and aren't changed by this feature.

## Helper functions (`src/works.py`)

- `_month_range(anchor_date: str) -> tuple[str, str]` — returns `(1st of last
  month relative to anchor_date, today)` as `YYYY-MM-DD` strings. Used both
  for step 1's bound (`anchor_date = today`) and step 3's bound (`anchor_date
  = selected_date`).
- `_prompt_date(label, default, min_date, max_date) -> str` — text prompt,
  extends `validate_date`'s format check with a range check against
  `[min_date, max_date]`.
- `_prompt_task_time(label, defaults) -> dict` — task/start/end prompts only
  (no date), returns `{work, time_start, time_end, hours}`. `_prompt_work_entry`
  becomes a thin wrapper: `_prompt_date(...)` + `_prompt_task_time(...)`,
  merged into the existing `{date, work, time_start, time_end, hours}` shape,
  so `edit_work_entry`/`clone_work_entry` need no changes.
- `_weekly_dates(selected_date, min_date, max_date) -> list[str]` — dates
  sharing `selected_date`'s weekday, 7 days apart, newest-first, within bound.
- `_daily_dates(min_date, max_date) -> list[str]` — every calendar date in
  the bound, newest-first.
- `prompt_weekly_until(selected_date, min_date, max_date) -> list[str]` —
  runs the mode-2 select, returns resolved `dates`.
- `prompt_multi_select_dates(selected_date, min_date, max_date) -> list[str]` —
  runs the mode-3 checkbox, returns resolved `dates`.
- `summarize_entries(dates, task_time) -> str` — mode-5 summary (split rows +
  shared warnings), replacing the single-entry `summarize_entry` call site in
  the new `add_works`. `summarize_entry` itself stays as-is (still used by
  `edit_work_entry`/`clone_work_entry`).

All new list/date helpers are pure functions (no I/O), matching the existing
`_demo()` testing convention.

## Error handling

- Date-range validation errors reuse questionary's inline validator message
  style (e.g. `Format: YYYY-MM-DD` becomes `Format: YYYY-MM-DD (between
  2026-07-01 and 2026-08-04)` when out of range).
- Per-date submit failures don't abort the batch — same resilience pattern as
  `delete_multiple_works`.
- `Ctrl-C`/cancel at any prompt raises `UserCancelled` and unwinds, same as
  every other flow in this file.

## Testing

Extend `_demo()` in `src/works.py` to cover the new pure helpers with fixed
dates (no network, no questionary):

- `_month_range` for a couple of anchor dates, including a same-day-as-1st
  edge case.
- `_weekly_dates` produces the right weekday-spaced, newest-first list and
  respects both bounds.
- `_daily_dates` produces a contiguous newest-first range including both
  endpoints.

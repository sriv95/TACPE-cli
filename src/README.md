# Development

Requires Python >=3.14 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sriv95/TACPE-csv-to-works
cd TACPE-csv-to-works
uv sync                              # install dependencies
uv run playwright install chromium   # browser for the Browser login method
uv run python -m src.main            # run the CLI
```

## Layout

- `main.py` entrypoint wiring the below into one flow
- `cli/` interactive top-level flows
  - `auth.py` login (Playwright browser flow or manual cookie paste), cookie persistence
  - `course.py` academic term + course/section selection
  - `work/` work-report flows
    - `works.py` view work entries, single-entry add, submit-to-API
    - `bulk_works.py` CSV bulk import
    - `timetable.py` recurring weekly enrolled-course schedule, persisted to `.cache/.timetable`
    - `auto_slot.py` Auto Find Slot: finds free start times around lunch/timetable/existing works, single and bulk CSV
- `func/` non-interactive core logic
  - `const.py` API endpoint constants
  - `request.py` shared HTTP helper, injects the session `Cookie` header globally
  - `update.py` self-update check
- `helper/` small reusable utilities
  - `prompt.py` cancel-safe questionary wrappers
  - `file.py` native file picker
  - `exceptions.py` shared `UserCancelled` exception for clean Ctrl+C / cancel handling

No test suite yet - verify changes with `uv run python -m src.main` against a real login. (bad)

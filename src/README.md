# Development

Requires Python >=3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                        # install dependencies
uv run python -m src.main      # run the CLI
```

## Layout

- `const.py` API endpoint constants
- `auth.py` login (Playwright browser flow or manual cookie paste), cookie persistence
- `request.py` shared HTTP helper, injects the session `Cookie` header globally
- `course.py` academic term + course/section selection
- `works.py` view work entries, single-entry add, submit-to-API
- `bulk_works.py` CSV bulk import
- `timetable.py` recurring weekly enrolled-course schedule, persisted to `.cache/.timetable`
- `auto_slot.py` Auto Find Slot: finds free start times around lunch/timetable/existing works, single and bulk CSV
- `exceptions.py` shared `UserCancelled` exception for clean Ctrl+C / cancel handling
- `main.py` entrypoint wiring the above into one flow

No test suite yet - verify changes with `uv run python -m src.main` against a real login. (bad)

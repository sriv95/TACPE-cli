# Changelog

## [v1.1.4] - 2026-09-01

### Added
- Month filter and pagination (15 entries/page) in the work entries view.
- Flexible date input (`DDMonYYYY`, e.g. `04Aug2026`) accepted alongside `YYYY-MM-DD` across work entry, clone, auto-slot, and bulk CSV rows.
- Round-up time parsing: minutes not on 00/30 round up to the next 00/30 (e.g. `19:45` → `20:00`), used for auto-slot earliest-start times.

### Changed
- Auto-slot "minimum start time" renamed to "earliest start time"; when given, it now picks the first free slot at/after that time instead of the 08:00/13:00/latest default.
- Bulk auto-slot CSV `startTime` description clarified (earliest start, round-up behavior).

## [v1.1.3] - 2026-08-12

### Added
- `Edit` option in `add_works` menu, letting you revise task time before submitting.
- Future-date warning when adding work entries.

### Changed
- Browser login prefers system Chrome/Edge over bundled Chromium, falling back if unavailable.
- Simplified date prompting in work entry: format-checked only, no min/max range restriction.

### Fixed
- Browser-closed-during-login now exits with a clear error instead of retrying.

## [v1.1.2] - 2026-08-12

### Added
- Installation scripts for Windows PowerShell and Bash (`scripts/install.ps1`, `scripts/install.sh`).

### Changed
- Fix Chromium install script for browser login

## [v1.1.1] - 2026-08-07

### Added
- `timetable` command with `add`, `edit`, and `delete` actions, plus JSON output option.
- `auto` command for finding and adding free work slots, with single and bulk options.
- `edit` and `delete` commands for work entries, with validation.
- Overlap checking command for work entries across courses.
- JSON output option for `list` (courses and work entries).
- Error handling for Playwright installation during login.
- `SKILL.md` documenting tacpe CLI commands and usage for AI agent integration.

### Changed
- Enhanced work entry validation with overlap checks and new options.
- Updated README prerequisites, installation instructions, and Agent Skill section.
- Refactored docstrings for clarity and consistency across modules.

### Removed
- Redundant command for running from a clone in README.

## [v1.1.0] - 2026-08-06

### Added
- Standalone CLI with argument parsing, per-command help descriptions, and a version command.
- `list` command for courses and works with term/year resolution.
- `submit` command for work entries, supporting single and bulk uploads.
- Login check and cookie validation before running commands; logout command for standalone CLI.

### Changed
- Simplified browser opening logic, removed Playwright integration.
- Refactored time handling with shared `split_time` function.
- Refactored work submission into shared `run_batch` utility.
- Renamed repository to TACPE-cli, updated URL references.
- Moved source files into a submodule.

### Fixed
- Browser subprocess stderr suppressed and process closed only when connected.

### Tests
- Added unit tests for time handling, CSV reading, and batch processing.

## [v1.0.1] - 2026-08-05

### Added
- Timetable view with loop for browsing and editing entries.
- Overlap checking for courses against the timetable.
- Browser launching for work report pages.
- Logout option that removes the saved cookie.

## [1.0.0] - 2026-08-05
First Release

[v1.1.4]: https://github.com/sriv95/TACPE-cli/compare/v1.1.3...v1.1.4
[v1.1.1]: https://github.com/sriv95/TACPE-cli/compare/v1.1.0...v1.1.1
[v1.1.0]: https://github.com/sriv95/TACPE-cli/compare/v1.0.1...v1.1.0
[v1.0.1]: https://github.com/sriv95/TACPE-cli/compare/v1.0.0...v1.0.1

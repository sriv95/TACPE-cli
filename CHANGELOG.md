# Changelog

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

[v1.1.1]: https://github.com/sriv95/TACPE-cli/compare/v1.1.0...v1.1.1
[v1.1.0]: https://github.com/sriv95/TACPE-cli/compare/v1.0.1...v1.1.0
[v1.0.1]: https://github.com/sriv95/TACPE-cli/compare/v1.0.0...v1.0.1

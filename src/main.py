import sys

from rich.console import Console

from src.cli.auth import login
from src.cli.course import select_course
from src.cli.standalone import run as run_standalone
from src.helper.exceptions import UserCancelled
from src.func.update import check_update
from src.cli.work.works import view_works

console = Console()


def main():
    """Run a standalone subcommand if given, else the full interactive CLI: login, select course, works menu."""
    try:
        if run_standalone():
            return
        check_update()
        login()
        while True:
            course_id, course_label = select_course()
            view_works(course_id, course_label)
    except (UserCancelled, KeyboardInterrupt):
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

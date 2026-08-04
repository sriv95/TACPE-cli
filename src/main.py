import sys

from rich.console import Console

from src.auth import login
from src.course import select_course
from src.exceptions import UserCancelled
from src.update import check_update
from src.works import view_works

console = Console()


def main():
    """Run the full CLI: login, select course, enter works menu."""
    try:
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

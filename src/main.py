import sys

from src.auth import login
from src.course import select_course
from src.exceptions import UserCancelled
from src.works import view_works


def main():
    try:
        login()
        course_id = select_course()
        view_works(course_id)
    except (UserCancelled, KeyboardInterrupt):
        sys.exit(130)


if __name__ == "__main__":
    main()

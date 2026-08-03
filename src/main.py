import sys

from src.auth import login
from src.course import select_course
from src.exceptions import UserCancelled
from src.works import view_works


def main():
    try:
        login()
        course_id, course_label = select_course()
        view_works(course_id, course_label)
    except (UserCancelled, KeyboardInterrupt):
        sys.exit(130)


if __name__ == "__main__":
    main()

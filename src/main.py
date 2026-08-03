import sys

from src.auth import login
from src.course import select_course
from src.exceptions import UserCancelled


def main():
    try:
        login()
        select_course()
    except (UserCancelled, KeyboardInterrupt):
        sys.exit(130)


if __name__ == "__main__":
    main()

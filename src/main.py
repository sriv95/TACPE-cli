import sys

from src.auth import login
from src.exceptions import UserCancelled


def main():
    try:
        login()
    except (UserCancelled, KeyboardInterrupt):
        sys.exit(130)


if __name__ == "__main__":
    main()

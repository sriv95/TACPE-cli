"""Non-interactive CLI subcommands (e.g. `tacpe login browser`), separate from the default interactive flow."""

import argparse

from src.cli.auth import login_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tacpe")
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login", help="Log in and save the session cookie")
    login_parser.add_argument("method", nargs="?", choices=["browser", "cookie"], default=None)

    return parser


def run(argv: list[str] | None = None) -> bool:
    """Parse argv for a standalone subcommand and run it.
    Output: (bool) True if a subcommand was handled (caller should not continue to the interactive flow).
    """
    args = build_parser().parse_args(argv)
    if args.command == "login":
        method = "manual" if args.method == "cookie" else args.method
        login_prompt(method)
        return True
    return False

"""Shared questionary helpers: cancel-safe .ask() and confirm-or-cancel."""

import questionary

from src.helper.exceptions import UserCancelled


def ask(question):
    """Run a questionary prompt, raising UserCancelled instead of returning None on Ctrl-C/Esc.
    Input: question - an unstarted questionary Question.
    Output: (Any) the prompt's answer.
    """
    answer = question.ask()
    if answer is None:
        raise UserCancelled
    return answer


def confirm_or_cancel(message: str, **kwargs) -> bool:
    """Ask a yes/no confirm, raising UserCancelled on cancel.
    Input: message (str), kwargs - passed to questionary.confirm.
    Output: (bool) the answer.
    """
    return ask(questionary.confirm(message, **kwargs))

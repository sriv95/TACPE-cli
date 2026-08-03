"""Shared HTTP request helper — injects the session Cookie header globally."""

import urllib.request

_cookie: str | None = None


def set_cookie(cookie: str) -> None:
    """Store the session cookie used by all future requests.
    Input: cookie (str) - raw Cookie header string.
    """
    global _cookie
    _cookie = cookie


def request(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> bytes:
    """Send an HTTP request with the stored Cookie header attached.
    Input: url (str), method (str), data (bytes | None), headers (dict | None).
    Output: (bytes) raw response body.
    """
    if _cookie is None:
        raise RuntimeError("No cookie set. Call set_cookie() first.")
    req = urllib.request.Request(url, data=data, headers={**(headers or {}), "Cookie": _cookie}, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.read()

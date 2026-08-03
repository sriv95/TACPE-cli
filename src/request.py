"""Shared HTTP request helper — injects the session Cookie header globally."""

import urllib.request

_cookie: str | None = None


def set_cookie(cookie: str) -> None:
    global _cookie
    _cookie = cookie


def request(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> bytes:
    if _cookie is None:
        raise RuntimeError("No cookie set. Call set_cookie() first.")
    req = urllib.request.Request(url, data=data, headers={**(headers or {}), "Cookie": _cookie}, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.read()

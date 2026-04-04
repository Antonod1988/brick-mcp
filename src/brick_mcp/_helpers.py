"""Shared response helpers for brick-mcp tools.

All tools return a dict with {"ok": bool, ...} envelope.
"""

from __future__ import annotations

from typing import Any


def ok(data: Any = None, message: str = "") -> dict:
    """Standard success response envelope."""
    result: dict = {"ok": True}
    if message:
        result["message"] = message
    if data is not None:
        result["data"] = data
    return result


def err(message: str, code: str = "ERROR") -> dict:
    """Standard error response envelope."""
    return {"ok": False, "error": {"code": code, "message": message}}

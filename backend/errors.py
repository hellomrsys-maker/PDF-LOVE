"""
errors — the one exception type every engine module shares.

This lives on its own, with no imports of its own, deliberately. engines.py
imports premium_pdf/ai_helper at the bottom of the file, and those modules
need EngineError; if they took it from engines.py the import graph would be
a cycle that only resolves when engines.py happens to be imported first.
Putting it here makes any import order work.
"""


class EngineError(Exception):
    """Raised by engine functions. `status` is the HTTP status the API layer
    should return; `detail` is a message safe to show a caller (never file
    contents or filenames)."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail

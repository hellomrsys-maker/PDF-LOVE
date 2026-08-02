"""The engine error type, in its own module so it can be shared without
creating an import cycle.

engines.py, premium_pdf.py, batch_pdf.py and ai_helper.py all need this
class, and several of them import each other. Keeping it here (a leaf
module that imports nothing) means none of them has to import another
just to raise an error. engines.py re-exports it, so the long-standing
`from engines import EngineError` keeps working.
"""


class EngineError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail

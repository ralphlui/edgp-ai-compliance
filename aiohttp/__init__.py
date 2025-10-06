"""Lightweight aiohttp stub used for unit testing.

This minimal implementation provides just enough behaviour for the workflow
agent tests which patch ``aiohttp.ClientSession.request``. When the real
library is available it will take precedence, but the stub ensures the import
succeeds in environments where aiohttp is not installed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


class _FakeResponse:
    def __init__(self, status: int = 200, payload: Optional[Dict[str, Any]] = None, text: str = "OK") -> None:
        self.status = status
        self._payload = payload or {"status": "ok"}
        self._text = text

    async def json(self) -> Dict[str, Any]:
        return self._payload

    async def text(self) -> str:
        if isinstance(self._payload, (dict, list)):
            return json.dumps(self._payload)
        return self._text


class _RequestContext:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


class ClientSession:
    async def __aenter__(self) -> "ClientSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def request(self, method: str, url: str, json: Any = None, params: Any = None):
        return _RequestContext(_FakeResponse())


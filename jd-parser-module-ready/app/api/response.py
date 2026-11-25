"""Custom JSONResponse subclass matching ECMAScript JSON.stringify byte-for-byte."""

from typing import Any

from starlette.responses import Response

from app.core.reward import js_json_stringify


class JSJSONResponse(Response):
    """Starlette response class that serializes response bodies with js_json_stringify."""

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        if content is None:
            return b"null"
        return js_json_stringify(content).encode("utf-8")

import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class DoubleEncodedJSONMiddleware:
    """Middleware to handle double-encoded JSON payloads from frontend.

    Some frontend clients may send JSON that's been stringified twice,
    resulting in payloads like '"{\"key\":\"value\"}"' instead of '{"key":"value"}'.
    This middleware detects and corrects such cases.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        raw_headers = scope.get("headers", [])
        scope_headers: list[tuple[bytes, bytes]] = [
            (name, value)
            for name, value in raw_headers
            if isinstance(name, bytes) and isinstance(value, bytes)
        ]
        headers: dict[bytes, bytes] = dict(scope_headers)
        content_type = headers.get(b"content-type", b"").decode("latin1")

        if method in ["POST", "PUT", "PATCH"] and content_type:
            body_parts: list[bytes] = []

            async def receive_wrapper() -> Message:
                message: Message = await receive()
                if message["type"] == "http.request":
                    body = message.get("body", b"")
                    if isinstance(body, (bytes, bytearray)):
                        body_parts.append(bytes(body))

                    if not message.get("more_body", False):
                        aggregated_body = b"".join(body_parts)

                        if aggregated_body:
                            try:
                                decoded = aggregated_body.decode("utf-8")
                                parsed = json.loads(decoded)

                                if isinstance(parsed, str):
                                    parsed = json.loads(parsed)

                                new_body = json.dumps(parsed).encode("utf-8")

                                if b"content-type" in headers and content_type != "application/json":
                                    new_headers: list[tuple[bytes, bytes]] = []
                                    for header_name, value in scope_headers:
                                        if header_name != b"content-type":
                                            new_headers.append((header_name, value))
                                    new_headers.append((b"content-type", b"application/json"))
                                    scope["headers"] = new_headers

                                return {
                                    "type": "http.request",
                                    "body": new_body,
                                    "more_body": False,
                                }
                            except (
                                json.JSONDecodeError,
                                ValueError,
                                UnicodeDecodeError,
                            ):
                                pass

                return message

            await self.app(scope, receive_wrapper, send)
        else:
            await self.app(scope, receive, send)

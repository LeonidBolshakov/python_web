import time
from typing import Awaitable
import inspect

from framework.exceptions import BadRequest
from framework.response import json_response
from framework.asgi_app import ASGIApp
from framework.types import (
    Scope,
    Receive,
    Send,
    Request,
    Handler,
    Response,
)


def logging_middleware(
    req: Request, handler: Handler
) -> Response | Awaitable[Response]:
    import time

    start = time.time()
    response = handler(req)
    duration_ms = (time.time() - start) * 1000
    print(f"{req.method} {req.path} {duration_ms:.2f} ms")
    return response


def error_middleware(req: Request, handler: Handler):

    try:
        result = handler(req)

        if inspect.isawaitable(result):

            async def wrapper():
                try:
                    return await result
                except BadRequest as e:
                    return json_response({"error": str(e)}, status=400)
                except Exception as e:
                    return json_response({"error": f"Internal Server Error {e}"}, status=500)

            return wrapper()

        return result

    except BadRequest as exc:
        return json_response({"error": str(exc)}, status=400)

    except Exception:
        return json_response({"error": "Internal Server Error"}, status=500)


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope["method"]
        path = scope["path"]

        try:
            await self.app(scope, receive, send)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            print(f"{method} {path} took {duration_ms:.2f} ms")


class ServerHeaderMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapper_send(message):

            if message["type"] == "http.response.start":
                message["headers"].append((b"server", b"my-asgi-framework"))

            await send(message)

        await self.app(scope, receive, wrapper_send)

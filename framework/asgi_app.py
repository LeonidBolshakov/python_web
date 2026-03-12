"""
ASGI-приложение для нашего учебного фреймворка.
"""

import inspect
import json
from urllib.parse import parse_qs
from typing import Any
from typing import Protocol

from framework.router import Router
from framework.response import Response
from framework.types import (
    Scope,
    Send,
    Receive,
    Request,
    Handler,
    Middleware,
    MiddlewareFactory,
)

class ASGIApp(Protocol):
    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None: ...


class App:
    """
    ASGI-приложение нашего учебного фреймворка.
    """

    def __init__(self) -> None:
        self.router = Router()

        # обычные middleware (handler level)
        self.middlewares: list[Middleware] = []

        # ASGI middleware
        self.asgi_middlewares: list[MiddlewareFactory] = []

        # кеш ASGI стека
        self._asgi_stack: ASGIApp | None = None

    # ---------------- ROUTES ----------------

    def add_route(self, path: str, method: str, handler: Handler) -> None:
        self.router.add(method, path, handler)

    def route(self, path: str, methods: list[str] | None = None):
        if methods is None:
            methods = ["GET"]

        def decorator(handler: Handler) -> Handler:
            for method in methods:
                self.add_route(path, method, handler)
            return handler

        return decorator

    def get(self, path: str):
        return self.route(path, ["GET"])

    def post(self, path: str):
        return self.route(path, ["POST"])

    # ---------------- MIDDLEWARE ----------------

    def add_middleware(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)

    def add_asgi_middleware(self, middleware: MiddlewareFactory) -> None:
        self.asgi_middlewares.append(middleware)
        self._asgi_stack = None

    # ---------------- RESPONSE ----------------

    def ensure_response(self, result: Any) -> Response:
        if isinstance(result, Response):
            return result

        if isinstance(result, dict):
            return Response(
                body=json.dumps(result).encode(),
                status=200,
                headers=[(b"content-type", b"application/json")],
            )

        if isinstance(result, str):
            return Response(
                body=result.encode(),
                status=200,
                headers=[(b"content-type", b"text/plain")],
            )

        raise TypeError("Handler должен возвращать Response, dict или str")

    # ---------------- HANDLER MIDDLEWARE CHAIN ----------------

    def _build_chain(self, handler: Handler) -> Handler:

        for mw in reversed(self.middlewares):
            next_handler = handler

            async def wrapper(request: Request, mw_=mw, nxt=next_handler):
                result = mw_(request, nxt)

                if inspect.isawaitable(result):
                    result = await result

                return result

            handler = wrapper

        return handler

    # ---------------- ASGI STACK ----------------

    def _build_asgi_stack(self) -> ASGIApp:

        if self._asgi_stack is not None:
            return self._asgi_stack

        app: ASGIApp = self._asgi_app

        for middleware in reversed(self.asgi_middlewares):
            app = middleware(app)


        self._asgi_stack = app
        return app

    # ---------------- ASGI ENTRYPOINT ----------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:

        app = self._build_asgi_stack()
        await app(scope, receive, send)

    # ---------------- INTERNAL ASGI APP ----------------

    async def _asgi_app(self, scope: Scope, receive: Receive, send: Send) -> None:

        if scope.get("type") != "http":
            return

        body = await self._receive_body(receive)
        request = self._make_request(scope, body)

        response = await self._dispatch(request)

        await self._send_response(send, response)

    # ---------------- BODY ----------------

    async def _receive_body(self, receive: Receive) -> bytes:

        body = b""
        while True:
            event = await receive()
            if event["type"] == "http.request":
                body += event.get("body", b"")
                if not event.get("more_body", False):
                    break
        return body

    # ---------------- REQUEST ----------------

    def _make_request(self, scope: Scope, body: bytes) -> Request:

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        headers = scope.get("headers", [])

        raw_qs = scope.get("query_string", b"")

        query_params = parse_qs(raw_qs.decode("latin-1")) if raw_qs else {}

        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query=query_params,
        )

    # ---------------- DISPATCH ----------------

    async def _dispatch(self, request: Request) -> Response:
        resolved = self.router.resolve(request.method, request.path)

        if resolved is None:
            return self._make_routing_error_response(request.path)

        handler, path_params = resolved
        request.path_params = path_params

        app_handler = self._build_chain(handler)
        result = await self._call_handler(app_handler, request)

        return self.ensure_response(result)

    def _make_routing_error_response(self, path: str) -> Response:
        allowed = self.router.allowed_methods(path)

        if allowed:
            allowed_str = ", ".join(allowed)
            return Response(
                body=json.dumps(
                    {"error": f"{path} supports only: {allowed_str}"}
                ).encode(),
                status=405,
                headers=[
                    (b"Allow", allowed_str.encode()),
                    (b"content-type", b"application/json"),
                ],
            )

        return Response(
            body=json.dumps({"error": f'Unknown path "{path}"'}).encode(),
            status=404,
            headers=[(b"content-type", b"application/json")],
        )

    async def _call_handler(self, handler, request: Request) -> Any:
        result = handler(request)

        if inspect.isawaitable(result):
            result = await result

        return result


    # ---------------- SEND RESPONSE ----------------

    async def _send_response(self, send: Send, response: Response) -> None:

        resp = response.with_default_headers()

        await send(
            {
                "type": "http.response.start",
                "status": resp.status,
                "headers": resp.headers,
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": resp.body,
            }
        )

"""
ASGI-приложение для нашего учебного фреймворка.
"""

import inspect
import json
from typing import Any, Protocol, Iterator
from urllib.parse import parse_qs
from pydantic import BaseModel, ValidationError

from framework.response import Response, ensure_response
from framework.router import Router
from framework.exceptions import BadRequest
from framework.depends import Depends
from framework.types import (
    Handler,
    Middleware,
    MiddlewareFactory,
    Receive,
    Request,
    Scope,
    Send,
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

        async def endpoint(req: Request) -> Any:
            return await self._call_handler(handler, req)

        app_handler = self._build_chain(endpoint)
        result = app_handler(request)

        if inspect.isawaitable(result):
            result = await result

        return ensure_response(result)

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

    async def _call_handler(self, handler: Handler, request: Request) -> Any:
        dependency_cache: dict[Any, Any] = {}
        cleanup: list[Iterator[Any]] = []

        kwargs = await self._build_kwargs(
            handler,
            request,
            dependency_cache,
            cleanup,
        )
        result = handler(**kwargs)

        if inspect.isawaitable(result):
            result = await result

        for gen in reversed(cleanup):
            try:
                next(gen)
            except StopIteration:
                pass

        return result

    async def _build_kwargs(
        self,
        handler: Handler,
        request: Request,
        dependency_cache: dict[Any, Any],
        cleanup: list[Iterator[Any]],
    ) -> dict[str, Any]:
        sig = inspect.signature(handler)
        kwargs: dict[str, Any] = {}

        body = request.json()

        for name, param in sig.parameters.items():
            if param.annotation is Request or name == "request":
                kwargs[name] = request
                continue

            if name in request.path_params:
                raw_value = request.path_params[name]
                try:
                    kwargs[name] = self._convert_type(raw_value, param.annotation)
                except (ValueError, TypeError):
                    raise BadRequest(
                        f"Некорректное значение path-параметра '{name}': {raw_value!r}"
                    )
                continue

            raw_value = request.query_param(name)
            if raw_value is not None:
                try:
                    kwargs[name] = self._convert_type(raw_value, param.annotation)
                except (ValueError, TypeError):
                    raise BadRequest(
                        f"Некорректное значение query-параметра '{name}': {raw_value!r}"
                    )
                continue

            if self._is_pyadantic_model(param.annotation):
                if not isinstance(body, dict):
                    raise BadRequest(f"Ожидался JSON-объект {body}")
                try:
                    kwargs[name] = param.annotation.model_validate(body)
                except ValidationError as e:
                    raise BadRequest(str(e))
                continue

            if isinstance(body, dict) and name in body:
                raw_value = body[name]
                try:
                    kwargs[name] = self._convert_type(raw_value, param.annotation)
                except (ValueError, TypeError):
                    raise BadRequest(
                        f"Некорректное значение body-параметра '{name}': {raw_value!r}"
                    )
                continue

            if isinstance(param.default, Depends):
                dep = param.default.dependency

                value = await self._resolve_dependency(
                    dep, request, dependency_cache, cleanup
                )

                kwargs[name] = value
                continue

            if param.default is not inspect._empty:
                kwargs[name] = param.default
                continue

            raise BadRequest(f"Отсутствует обязательный параметр: '{name}'")

        return kwargs

    async def _resolve_dependency(
        self,
        dep,
        request: Request,
        dependency_cache: dict[Any, Any],
        cleanup: list[Iterator[Any]],
    ) -> Any:
        if dep in dependency_cache:
            return dependency_cache[dep]

        kwargs = await self._build_kwargs(dep, request, dependency_cache, cleanup)

        if inspect.isgeneratorfunction(dep):
            generator = dep(**kwargs)
            value = next(generator)
            cleanup.append(generator)
        else:
            value = dep(**kwargs)
            if inspect.isawaitable(value):
                value = await value

        dependency_cache[dep] = value
        return value

    def _is_pyadantic_model(self, annotation: Any) -> bool:
        return inspect.isclass(annotation) and issubclass(annotation, BaseModel)

    def _convert_type(self, value: Any, annotation: Any) -> Any:
        if annotation is inspect._empty or annotation is Any:
            return value

        if annotation is str:
            return str(value)

        if annotation is int:
            return int(value)

        if annotation is float:
            return float(value)

        if annotation is bool:
            if isinstance(value, bool):
                return value

            text = str(value).strip().lower()

            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False

            raise ValueError(f"Некорректное bool-значение: {value!r}")

        if annotation is bytes:
            if isinstance(value, bytes):
                return value
            return str(value).encode("utf-8")

        return value

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

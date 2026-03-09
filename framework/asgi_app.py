import inspect
import json
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from request import Request
from response import Response


class ASGIApp:
    def __init__(self, router, middlewares=None):
        self.router = router
        self.middlewares = middlewares or []

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        if not self._is_http_scope(scope):
            return

        method, path, headers, query_string = self._extract_request_parts(scope)
        body = await self._read_body(receive)
        request = self._make_request(method, path, headers, body, query_string)

        response = await self._dispatch_request(request)
        await self._send_response(send, response)

    def _is_http_scope(self, scope: Dict[str, Any]) -> bool:
        return scope.get("type") == "http"

    def _extract_request_parts(
        self, scope: Dict[str, Any]
    ) -> Tuple[str, str, List[Tuple[bytes, bytes]], bytes]:
        method: str = scope.get("method", "GET")
        path: str = scope.get("path", "/")
        headers = scope.get("headers", [])
        query_string: bytes = scope.get("query_string", b"")
        return method, path, headers, query_string

    async def _read_body(
        self,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> bytes:
        body = b""

        while True:
            event = await receive()
            event_type = event.get("type")

            if event_type == "http.disconnect":
                break

            if event_type != "http.request":
                continue

            body += event.get("body", b"")

            if not event.get("more_body", False):
                break

        return body

    def _make_request(
        self,
        method: str,
        path: str,
        headers: List[Tuple[bytes, bytes]],
        body: bytes,
        query_string: bytes,
    ) -> Request:
        return Request(
            method=method,
            path=path,
            headers=headers,
            body=body,
            query=query_string,
        )

    async def _dispatch_request(self, request: Request) -> Response:
        resolved = self.router.resolve(request.method, request.path)

        if resolved is None:
            return self._make_error_response(request.path)

        handler, path_params = resolved
        request.path_params = path_params

        app_handler = self._build_chain(handler)
        result = app_handler(request)

        if inspect.isawaitable(result):
            result = await result

        return self.ensure_response(result)

    def _make_error_response(self, path: str) -> Response:
        allowed = self.router.allowed_methods(path)

        if allowed:
            allowed_str = ", ".join(allowed)
            payload = {"error": f"{path} supports only: {allowed_str}"}
            return Response(
                body=json.dumps(payload).encode("utf-8"),
                status=405,
                headers=[
                    (b"Allow", allowed_str.encode()),
                    (b"content-type", b"application/json"),
                ],
            )

        payload = {"error": f'Unknown path "{path}"'}
        return Response(
            body=json.dumps(payload).encode("utf-8"),
            status=404,
            headers=[(b"content-type", b"application/json")],
        )

    async def _send_response(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        response: Response,
    ) -> None:
        response = response.with_default_headers()

        await send(
            {
                "type": "http.response.start",
                "status": response.status,
                "headers": response.headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": response.body,
            }
        )

    def _build_chain(self, handler):
        app_handler = handler
        for middleware in reversed(self.middlewares):
            app_handler = middleware(app_handler)
        return app_handler

    def ensure_response(self, result) -> Response:
        if isinstance(result, Response):
            return result

        if isinstance(result, bytes):
            return Response(body=result)

        if isinstance(result, str):
            return Response(body=result.encode("utf-8"))

        if isinstance(result, dict):
            return Response(
                body=json.dumps(result).encode("utf-8"),
                headers=[(b"content-type", b"application/json")],
            )

        return Response(body=str(result).encode("utf-8"))

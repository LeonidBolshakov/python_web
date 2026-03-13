from __future__ import annotations

import contextvars
import datetime as dt
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs

# ====== HTTP primitives ======

_request_var = contextvars.ContextVar("request")


def get_request() -> "Request":
    return _request_var.get()


@dataclass(frozen=True)
class Response:
    status: str
    headers: list[tuple[str, str]]
    body: bytes


def json_response(
    data: Any,
    status: str = "200 OK",
    headers: list[tuple[str, str]] | None = None,
) -> Response:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    h = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    if headers:
        h.extend(headers)
    return Response(status=status, headers=h, body=payload)


def text_response(
    text: str,
    status: str = "200 OK",
    headers: list[tuple[str, str]] | None = None,
) -> Response:
    payload = text.encode("utf-8")
    h = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    if headers:
        h.extend(headers)
    return Response(status=status, headers=h, body=payload)


# ====== Request helpers ======


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))


def _get_headers(environ: dict) -> dict[str, str]:
    headers: dict[str, str] = {}

    for k, v in environ.items():
        if k.startswith("HTTP_"):
            name = k[5:].replace("_", "-").title()
            headers[name] = v

    if "CONTENT_TYPE" in environ:
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if "CONTENT_LENGTH" in environ:
        headers["Content-Length"] = environ["CONTENT_LENGTH"]

    return headers


def _read_body(environ: dict) -> bytes:
    try:
        length_str = environ.get("CONTENT_LENGTH") or "0"
        length = int(length_str) if length_str else 0
    except ValueError:
        length = 0

    if length <= 0:
        return b""

    return environ["wsgi.input"].read(length)


def build_request(environ: dict) -> Request:
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"
    query_string = environ.get("QUERY_STRING") or ""
    query = parse_qs(query_string, keep_blank_values=True)
    headers = _get_headers(environ)
    body = _read_body(environ)

    return Request(
        method=method,
        path=path,
        query=query,
        headers=headers,
        body=body,
    )


# ====== Routing ======

Handler = Callable[[Request], Response]
Middleware = Callable[[Request, Handler], Response]


class Router:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Handler] = {}

    def add(self, method: str, path: str, handler: Handler) -> None:
        self.routes[(method.upper(), path)] = handler

    def allowed_methods(self, path: str) -> list[str]:
        methods = [m for (m, p) in self.routes.keys() if p == path]
        methods.sort()
        return methods

    def resolve(self, method: str, path: str) -> Handler | None:
        return self.routes.get((method.upper(), path))


# ====== Application ======


class App:
    def __init__(self) -> None:
        self.router = Router()
        self.middlewares: list[Middleware] = []

        self._register_routes()

        # logging снаружи, чтобы видеть и 500 тоже
        self.add_middleware(self.logging_middleware)
        self.add_middleware(self.error_middleware)

    def _register_routes(self) -> None:
        self.router.add("GET", "/", self.handle_index)
        self.router.add("GET", "/time", self.handle_time)
        self.router.add("GET", "/hello", self.handle_hello)
        self.router.add("POST", "/operation", self.handle_operation)

    # ---- handlers ----

    def handle_index(self, req: Request) -> Response:
        items = [f"{m} {p}" for (m, p) in sorted(self.router.routes.keys())]
        return json_response(items)

    def handle_time(self, req: Request) -> Response:
        return json_response({"now": dt.datetime.now().isoformat(timespec="seconds")})

    def handle_hello(self, req: Request) -> Response:
        name = (req.query.get("name") or ["world"])[0]
        return json_response({"message": f"Hello, {name}!"})

    def handle_operation(self, req: Request) -> Response:
        try:
            data = req.json() or {}
        except json.JSONDecodeError:
            return json_response({"error": "Invalid JSON"}, status="400 Bad Request")

        a = data.get("a")
        b = data.get("b")
        op = data.get("op")

        if a is None or b is None or op is None:
            return json_response(
                {"error": "Expected fields: a, b, op"},
                status="400 Bad Request",
            )

        try:
            a_num = float(a)
            b_num = float(b)
        except (TypeError, ValueError):
            return json_response(
                {"error": "a and b must be numbers"},
                status="400 Bad Request",
            )

        if op == "sum":
            result = a_num + b_num
        elif op == "multiply":
            result = a_num * b_num
        else:
            return json_response(
                {"error": f"Unknown op: {op}"},
                status="400 Bad Request",
            )

        return json_response({"result": result})

    # ---- middlewares ----

    def add_middleware(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)

    def _build_chain(self, handler: Handler) -> Handler:
        for middleware in reversed(self.middlewares):
            next_handler = handler

            def wrapper(req: Request, mw=middleware, nxt=next_handler) -> Response:
                return mw(req, nxt)

            handler = wrapper

        return handler

    def logging_middleware(self, req: Request, handler: Handler) -> Response:
        start = time.perf_counter()
        response = handler(req)
        duration_ms = (time.perf_counter() - start) * 1000

        print(f"{req.method} {req.path} -> {response.status} {duration_ms:.2f} ms")
        return response

    def error_middleware(self, req: Request, handler: Handler) -> Response:
        try:
            return handler(req)
        except Exception as e:
            return json_response(
                {"error": "Internal Server Error", "detail": str(e)},
                status="500 Internal Server Error",
            )

    # ---- WSGI entrypoint ----

    def __call__(self, environ: dict, start_response) -> Iterable[bytes]:
        req = build_request(environ)
        token = _request_var.set(req)

        try:
            handler = self.router.resolve(req.method, req.path)

            if handler is None:
                allowed = self.router.allowed_methods(req.path)

                if allowed:
                    resp = json_response(
                        {"error": f"{req.path} supports only: {', '.join(allowed)}"},
                        status="405 Method is Not Allowed",
                        headers=[("Allow", ", ".join(allowed))],
                    )
                else:
                    resp = json_response(
                        {"error": f'Неизвестный путь "{req.path}"'},
                        status="404 Not Found",
                    )
            else:
                app_handler = self._build_chain(handler)
                resp = app_handler(req)

            start_response(resp.status, resp.headers)
            return [resp.body]
        finally:
            _request_var.reset(token)


app = App()

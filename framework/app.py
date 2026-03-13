from typing import Iterable

from framework.response import Response, json_response, text_response
from framework.router import Router
from framework.types import Handler, Middleware
from framework.wsgi_adapter import build_request


class App:
    def __init__(self) -> None:
        self.router = Router()
        self.middlewares: list[Middleware] = []

    def add_route(self, path: str, method: str, handler: Handler) -> None:
        self.router.add(method, path, handler)

    def add_middleware(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)

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

    def ensure_response(self, result) -> Response:
        if isinstance(result, Response):
            return result
        if isinstance(result, dict):
            return json_response(result)
        if isinstance(result, str):
            return text_response(result)
        raise TypeError("Handler должен возвращать Response, dict или str")

    def _build_chain(self, handler: Handler) -> Handler:
        for middleware in reversed(self.middlewares):
            next_handler = handler

            def wrapper(req, mw=middleware, nxt=next_handler):
                return mw(req, nxt)

            handler = wrapper

        return handler

    def __call__(self, environ: dict, start_response) -> Iterable[bytes]:
        req = build_request(environ)

        resolved = self.router.resolve(req.method, req.path)

        if resolved is None:
            allowed = self.router.allowed_methods(req.path)
            if allowed:
                resp = json_response(
                    {"error": f'{req.path} supports only: {", ".join(allowed)}'},
                    status="405 Method is Not Allowed",
                    headers=[("Allow", ", ".join(allowed))],
                )
            else:
                resp = json_response(
                    {"error": f'Unknown path "{req.path}"'},
                    status="404 Not Found",
                )
        else:
            handler, path_params = resolved
            req.path_params = path_params
            app_handler = self._build_chain(handler)
            result = app_handler(req)
            resp = self.ensure_response(result)

        start_response(resp.status, resp.headers)
        return [resp.body]

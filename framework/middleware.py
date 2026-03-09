from typing import Callable, Any

from framework.request import Request
from framework.response import Response, json_response

Handler = Callable[[Request], Any]
Middleware = Callable[[Request, Handler], Response]


def logging_middleware(req: Request, handler: Handler) -> Response:
    import time

    start = time.time()
    response = handler(req)
    duration_ms = (time.time() - start) * 1000
    print(f"{req.method} {req.path} {duration_ms:.2f} ms")
    return response


def error_middleware(req: Request, handler: Handler) -> Response:
    try:
        return handler(req)
    except Exception as exc:
        return json_response(
            {"error": "Internal Server Error", "detail": str(exc)},
            status="500 Internal Server Error",
        )

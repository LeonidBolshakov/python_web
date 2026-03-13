from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias

from framework.request import Request
from framework.response import Response

if TYPE_CHECKING:
    from framework.asgi_app import ASGIApp  # noqa: F401

# ---- ASGI типы ----

Scope = dict[str, Any]
Message = dict[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# ---- Framework типы ----

HandlerResult: TypeAlias = Response | Awaitable[Response]
Handler: TypeAlias = Callable[[Request], HandlerResult]
Middleware: TypeAlias = Callable[[Request, Handler], HandlerResult]
MiddlewareFactory = Callable[["ASGIApp"], "ASGIApp"]

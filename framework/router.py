import re
from dataclasses import dataclass

from framework.types import Handler


def compile_path(path: str) -> re.Pattern[str]:
    pattern = re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", path)
    return re.compile(f"^{pattern}$")


@dataclass
class Route:
    method: str
    path: str
    pattern: re.Pattern[str]
    handler: Handler


class Router:
    def __init__(self) -> None:
        self.routes: list[Route] = []

    def add(self, method: str, path: str, handler: Handler) -> None:
        self.routes.append(
            Route(
                method=method.upper(),
                path=path,
                pattern=compile_path(path),
                handler=handler,
            )
        )

    def allowed_methods(self, path: str) -> list[str]:
        methods: list[str] = []

        for route in self.routes:
            if route.pattern.match(path):
                methods.append(route.method)

        methods.sort()
        return methods

    def resolve(self, method: str, path: str) -> tuple[Handler, dict[str, str]] | None:
        for route in self.routes:
            if route.method != method.upper():
                continue

            match = route.pattern.match(path)
            if match:
                return route.handler, match.groupdict()

        return None

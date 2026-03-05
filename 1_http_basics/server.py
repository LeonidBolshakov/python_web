from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Any


def route(method: str, path: str):
    def decorator(func):
        func.__route__ = (method, path)
        return func

    return decorator


class Operator(Enum):
    add = "sum"
    mul = "mul"
    pow = "pow"
    div = "div"


@dataclass
class Result:
    ok: bool
    value: Any = None
    status_code: int = None
    error: str | None = None
    allowed_methods: str | None = None


class RouterMixin:
    ROUTES: dict[tuple[str, str], str] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.ROUTES = cls.build_routes()

    @classmethod
    def build_routes(cls):
        routes = {}
        for name, obj in cls.__dict__.items():
            if callable(obj) and hasattr(obj, "__route__"):
                routes[obj.__route__] = name
        return routes


class SimpleHandler(RouterMixin, BaseHTTPRequestHandler):
    def send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(status)
        self.send_header(
            keyword="Content-type", value="application/json; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def send_text(self, status: int, text: str) -> None:
        self.send_response(status)
        self.send_header(keyword="Content-type", value="text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def read_json_body(
        self,
    ) -> tuple[dict[str, object] | None, dict[str, str] | None, int | None]:
        """
        Возвращает tuple (data, error_dict, status_code).
        Если всё ок: (data, None, None)
        Если ошибка: (None, {"error": "..."} , <status>)
        """
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            return None, {"error": "Content-Type должен быть application/json"}, 415

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return None, {"error": "Пустое тело запроса"}, 400

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            return (
                None,
                {
                    "error": "Тело запроса пришло не полностью (Content-Length не совпал)"
                },
                400,
            )

        try:
            data = json.loads(body.decode("utf-8"))
        except UnicodeDecodeError:
            return None, {"error": "Тело запроса должно быть UTF-8"}, 400
        except json.JSONDecodeError:
            return None, {"error": "Неверный JSON"}, 400

        if not isinstance(data, dict):
            return None, {"error": "JSON должен быть объектом (словарём)"}, 400

        return data, None, None

    @route("POST", "/operation")
    def calculate(self, data: dict, query=None, params=None) -> Result:
        number_result = self.extract_numbers(data)
        if not number_result.ok:
            return number_result

        operator, a, b = number_result.value

        match operator:
            case Operator.add.value:
                calc_result = a + b
            case Operator.mul.value:
                calc_result = a * b
            case Operator.pow.value:
                calc_result = a**b
            case Operator.div.value:
                try:
                    calc_result = a / b
                except ZeroDivisionError:
                    return Result(
                        ok=False, status_code=422, error="'b' не должно быть нулём"
                    )
            case _:
                return Result(
                    ok=False, status_code=422, error=f"Недопустимая операция {operator}"
                )

        return Result(ok=True, value=calc_result)

    def extract_numbers(self, data: dict[str, object]) -> Result:
        a = data.get("a")
        b = data.get("b")
        operation = data.get("operation")

        if a is None or b is None or operation is None:
            return Result(
                ok=False,
                status_code=422,
                error="Параметры 'a', 'b' и 'operation' обязательны",
            )

        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return Result(
                ok=False,
                status_code=422,
                error="Параметры 'a' и 'b' должны быть числами",
            )

        return Result(ok=True, value=(operation, a, b))

    @route("POST", "/echo")
    def handle_echo(self, data: dict[str, object], query=None, params=None) -> Result:
        return Result(ok=True, value={"received": data})

    @route("GET", "/time")
    def handle_time(self, data=None, query=None, params=None) -> Result:
        return Result(ok=True, value={"time": datetime.now().isoformat()})

    @route("GET", "/hello")
    def handler_hello(
        self,
        data: dict[str, object] | None = None,
        query: dict[str, list[str]] | None = None,
        params=None,
    ) -> Result:
        name = None
        if query:
            name = query.get("name", [None])[0]
        if name:
            return Result(ok=True, value={"message": f"Привет {name}!"})
        return Result(ok=False, status_code=400, error="Параметр 'name' обязателен")

    @route("GET", "/users/<user_id>")
    def handle_user_by_id(
        self,
        data: dict[str, object] | None = None,
        query: dict[str, list[str]] | None = None,
        path_params: dict[str, str] | None = None,
    ) -> Result:

        if not path_params or "user_id" not in path_params:
            return Result(
                ok=False, status_code=500, error="path_params не содержит user_id"
            )

        raw = path_params["user_id"]
        try:
            user_id = int(raw)
        except ValueError:
            return Result(
                ok=False, status_code=400, error="user_id должен быть целым числом"
            )
        return Result(ok=True, value={"user_id": user_id})

    @route("GET", "/")
    def handle_root(self, data=None, query=None, params=None) -> Result:
        return Result(
            ok=True,
            value={
                "message": "OK",
                "endpoints": [
                    "GET /time",
                    "GET /hello?name=Ivan",
                    "GET /users/<user_id>",
                    "POST /operation",
                ],
            },
        )

    def send_method_not_allowed(
        self, allowed_methods: str, message: str = "Method is Not Allowed"
    ) -> None:
        # allowed_methods.
        self.send_response(405)
        self.send_header("Allow", allowed_methods)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return None

        # query
        params = parse_qs(parsed.query)
        result = self.dispatch("GET", path, data=None, query=params)

        return self.respond(result)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        data, err, status = self.read_json_body()
        if data is None:
            if status is not None and err is not None:
                return self.send_json(status=status, data=err)
            return self.send_json(status=500, data={"error": "Ошибка в программе"})

        result = self.dispatch("POST", path, data=data, query=None)

        return self.respond(result, ok_wrapper="result")

    def dispatch(
        self,
        method: str,
        path: str,
        data: dict[str, object] | None = None,
        query: dict[str, list[str]] | None = None,
    ) -> Result:

        handler_name, path_params, allowed_methods = self.parse_path(method, path)
        if allowed_methods is not None and handler_name is None:
            return Result(
                ok=False,
                status_code=405,
                error=f"{path} поддерживает только {allowed_methods}",
                allowed_methods=allowed_methods,
            )

        if handler_name is None:
            return Result(ok=False, status_code=404, error=f'Неверный path "{path}"')

        handler = getattr(self, handler_name, None)
        if handler is None:
            return Result(ok=False, status_code=500, error="Handler не найден")

        return handler(data, query, path_params)

    def parse_path(
        self, method: str, path: str
    ) -> tuple[str | None, dict[str, str] | None, str | None]:
        # 1) Точное совпадение
        handler_name = self.ROUTES.get((method, path))
        if handler_name is not None:
            return handler_name, None, None

        allowed: set[str] = set()
        for (route_method, route_path), route_handler in self.ROUTES.items():
            # проверка совпадения path с route_path (точно или по шаблону)
            route_parts = route_path.strip("/").split("/")
            path_parts = path.strip("/").split("/")

            if len(route_parts) != len(path_parts):
                continue

            params: dict[str, str] = {}
            matched = True

            for rp, pp in zip(route_parts, path_parts):
                if rp.startswith("<") and rp.endswith(">"):
                    param_name = rp[1:-1]
                    if not param_name:
                        matched = False
                        break
                    params[param_name] = pp
                else:
                    if rp != pp:
                        matched = False
                        break

            if not matched:
                continue

            # path совпал. значит этот route_path существует, просто метод может быть другой
            allowed.add(route_method)

            # если метод совпал — это наш хендлер
            if route_method == method:
                return route_handler, params, None

        # если path существует, но method не тот — 405
        if allowed:
            return None, None, ",".join(sorted(allowed))

        # иначе вообще не найден
        return None, None, None

    def respond(self, result: Result, ok_wrapper: str | None = None) -> None:
        if result.ok:
            if ok_wrapper is None:
                return self.send_json(200, result.value)
            return self.send_json(200, {ok_wrapper: result.value})

        if result.status_code == 405 and result.allowed_methods:
            return self.send_method_not_allowed(
                result.allowed_methods,
                result.error or "Недопустимый метод",
            )

        status = result.status_code or 500
        return self.send_json(status, {"error": result.error or "Ошибка"})


if __name__ == "__main__":
    server_address = ("localhost", 8000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Server started at http://localhost:8000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server остановлен")

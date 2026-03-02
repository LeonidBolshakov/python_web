from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime
from enum import Enum


class operator(Enum):
    add = "/sum"
    mul = "/mul"
    pow = "/pow"


class SimpleHandler(BaseHTTPRequestHandler):
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

    def extract_numbers(
        self, data: dict[str, object]
    ) -> tuple[int | float, int | float] | None:
        a = data.get("a")
        b = data.get("b")

        if a is None or b is None:
            self.send_json(
                status=422, data={"error": "Параметры 'a' и 'b' обязательны"}
            )
            return None

        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            self.send_json(
                status=422, data={"error": "Параметры 'a' и 'b' должны быть числами"}
            )
            return None

        return a, b

    def handle_sum(self, data: dict[str, object]) -> None:
        if (r := self.extract_numbers(data)) is None:
            return None

        a, b = r

        return self.send_json(status=200, data={"result": a + b})

    def handle_echo(self, data: dict[str, object]) -> None:
        return self.send_json(200, {"received": data})

    def handle_multiply(self, data: dict[str, object]) -> None:
        if (r := self.extract_numbers(data)) is None:
            return None

        a, b = r
        return self.send_json(status=200, data={"result": a * b})

    def handle_divide(self, data: dict[str, object]) -> None:
        if (r := self.extract_numbers(data)) is None:
            return None

        a, b = r

        try:
            result = a / b
        except ZeroDivisionError:
            return self.send_json(422, {"error": "'b' не должно быть нулём"})

        return self.send_json(200, {"result": result})

    def handle_power(self, data: dict[str, object]) -> None:
        if (r := self.extract_numbers(data)) is None:
            return None

        a, b = r

        result = a**b
        return self.send_json(200, {"result": result})

    def calculate(self, data: dict[str, object], operation) -> None:
        math
        a, b = self.extract_numbers(data)

    def send_method_not_allowed(
        self, allowed_methods: str, message: str = "Method is Not Allowed"
    ) -> None:
        # allowed_methods: например "POST" или "GET, POST"
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
        if path in ("/sum", "/echo", "/multiply", "/divide"):
            return self.send_method_not_allowed(
                allowed_methods="POST", message=f"{path} поддерживает только POST"
            )

        params = parse_qs(parsed.query)

        # favicon — отдаём 404 и выходим
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return None

        if path == "/":
            return self.send_text(status=200, text="Сервер запущен")

        if path == "/hello":
            name = params.get("name", [None])[0]
            if name:
                self.send_text(status=200, text=f"Привет {name}!")
            else:
                self.send_text(
                    status=400, text="Неверный запрос. Параметр 'name' обязателен"
                )
            return None

        if parsed.path.startswith("/users/"):
            user_part = path[len("/users/") :]
            if not user_part:
                return self.send_json(
                    status=400, data={"error": "Неверный запрос: отсутствует user_id"}
                )
            try:
                user_id = int(user_part)
            except ValueError:
                return self.send_json(
                    status=400, data={"error": "user_id должен быть числом"}
                )
            self.send_json(status=200, data={"user_id": user_id})

        if parsed.path == "/time":
            return self.send_json(200, {"time": f"time = {datetime.now().isoformat()}"})

        return self.send_text(404, f"Неизветсная команда {parsed.path}")

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        data, err, status = self.read_json_body()
        if data is None:
            if status is not None and err is not None:
                return self.send_json(status=status, data=err)
            return self.send_json(status=500, data={"error": "Ошибка в программе"})

        if path == "/sum":
            return self.handle_sum(data=data)

        if path == "/echo":
            return self.handle_echo(data=data)

        if path == "/multiply":
            return self.handle_multiply(data=data)

        if path == "/divide":
            return self.handle_divide(data=data)

        if path == "/power":
            return self.handle_power(data=data)

        return self.send_json(404, {"error": f"Неизвестный endpoint: {path}"})


if __name__ == "__main__":
    server_address = ("localhost", 8000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Server started at http://localhost:8000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server остановлен")

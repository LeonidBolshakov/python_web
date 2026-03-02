from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime


class SimpleHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False)
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def send_text(self, status, text):
        self.send_response(status)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def read_json_body(self):
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

    def handle_sum(self, data: dict):
        if "a" not in data or "b" not in data:
            return self.send_json(400, {"error": "Поля a и b обязательны"})

        a, b = data["a"], data["b"]

        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return self.send_json(400, {"error": "Поля a и b должны быть числами"})

        return self.send_json(200, {"result": a + b})

    def handle_echo(self, data: dict):
        return self.send_json(200, {"received": data})

    def send_method_not_allowed(
        self, allowed_methods: str, message: str = "Method is Not Allowed"
    ):
        # allowed_methods: например "POST" или "GET, POST"
        self.send_response(405)
        self.send_header("Allow", allowed_methods)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        )

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/sum", "/echo"):
            self.send_method_not_allowed("POST", f"{path} поддерживает только POST")
        return

        params = parse_qs(parsed.query)

        # favicon — отдаём 404 и выходим
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return

        if path == "/":
            self.send_text(200, "Сервер запущен")
            return

        if path == "/hello":
            name = params.get("name", [None])[0]
            if name:
                self.send_text(200, f"Привет {name}!")
            else:
                self.send_text(400, "Неверный запрос. Параметр 'name' обязателен")
            return

        if parsed.path == "/sum":
            if "a" in params and "b" in params:
                try:
                    a = int(params["a"][0])
                    b = int(params["b"][0])
                except (KeyError, ValueError):
                    self.send_json(
                        400,
                        {"error": "Неверный запрос: a и b должны быть целыми числами."},
                    )
                    return
                self.send_json(200, {"result": a + b})
                return

        if parsed.path.startswith("/users/"):
            user_part = path[len("/users/") :]
            if not user_part:
                self.send_json(400, {"error": "Неверный запрос: отсутствует user_id"})
                return
            try:
                user_id = int(user_part)
            except ValueError:
                self.send_json(400, {"error": "user_id должен быть числом"})
                return
            self.send_json(200, {"user_id": user_id})

        if parsed.path == "/multiply":
            print(params)
            if "a" in params and "b" in params:
                try:
                    a = int(params["a"][0])
                    b = int(params["b"][0])
                except ValueError:
                    self.send_json(400, {"error": "a и b должны быть целыми числами"})
                    return
                self.send_json(200, {"result": a * b})
                return
            else:
                self.send_json(400, {"error": "Отсутствуют a и/или b"})
                return

        if parsed.path == "/divide":
            if "a" in params and "b" in params:
                try:
                    a = int(params["a"][0])
                    b = int(params["b"][0])
                except ValueError:
                    self.send_json(400, {"error": "a и b должны быть целыми числами"})
                    return
                try:
                    self.send_json(200, {"result": a / b})
                    return
                except ZeroDivisionError:
                    self.send_json(400, {"error": "b не должно быть равно нулю"})
                    return
            else:
                self.send_json(400, {"error": "Отсутствуют a и/или b"})
                return

        if parsed.path == "/time":
            self.send_json(200, {"time": f"time = {datetime.now().isoformat()}"})
            return

        self.send_text(404, f"Неизветсная команда {parsed.path}")

    def do_POST(self):
        path = urlparse(self.path).path

        data, err, status = self.read_json_body()
        if err is not None:
            return self.send_json(status, err)

        if path == "/sum":
            return self.handle_sum(data)

        if path == "/echo":
            return self.handle_echo(data)

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

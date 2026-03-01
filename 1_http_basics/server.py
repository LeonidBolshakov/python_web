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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
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


if __name__ == "__main__":
    server_address = ("localhost", 8000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Server started at http://localhost:8000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server остановлен")

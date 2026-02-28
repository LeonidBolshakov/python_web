from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        # favicon — отдаём 404 и выходим
        if parsed.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return

        status = 200
        body = ""

        if parsed.path == "/sum":
            params = parse_qs(parsed.query)
            if "a" in params and "b" in params:
                try:
                    a = int(params["a"][0])
                    b = int(params["b"][0])
                    body = str(a + b)
                except ValueError:
                    status = 400
                    body = "Неверный запрос: a и b должны быть целыми числами."
            else:
                status = 400
                body = "Неверный запрос: a и b должны быть заданы"
        elif parsed.path == "/hello":
            body= "Привет из ветки разработки новых функций"
        else:
            status = 404
            body = "Не найден"

        self.send_response(status)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")

        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

        self.wfile.write(f"POST received. Body: {body}".encode("utf-8"))

if __name__ == "__main__":
    server_address = ("localhost", 8000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Server started at http://localhost:8000")
    httpd.serve_forever()
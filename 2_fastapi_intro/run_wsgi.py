from wsgiref.simple_server import make_server
from wsgi_app import app

if __name__ == "__main__":
    with make_server("127.0.0.1", 8000, app) as httpd:
        print("Сервер запущен по адресу: http://127.0.0.1:8000")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Сервер остановлен")

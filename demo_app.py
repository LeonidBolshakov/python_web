import datetime as dt

from framework.asgi_app import App
from framework.middleware import (
    LoggingMiddleware,
    ServerHeaderMiddleware,
    error_middleware,
    logging_middleware,
)
from framework.response import json_response, text_response
from framework.types import Request

app = App()

# handler middleware
app.add_middleware(logging_middleware)
app.add_middleware(error_middleware)


@app.get("/")
def handle_index(req: Request):
    lines = [
        f"{route.method:6} {route.path:20} -> {route.handler.__name__}"
        for route in app.router.routes
    ]
    return text_response("\n".join(lines))


@app.get("/time")
def handle_time(req: Request):
    return json_response({"now": dt.datetime.now().isoformat(timespec="seconds")})


@app.get("/hello")
def handle_hello(name: str = "Мир"):
    return json_response({"message": f"Hello, {name}!"})


@app.get("/users/<user_id>")
def handle_user(user_id: str):
    # user_id = req.path_params["user_id"]
    return json_response({"user_id": user_id})


@app.post("/operation")
def handle_operation(req: Request):
    data = req.json() or {}

    a = data.get("a")
    b = data.get("b")
    op = data.get("op")

    if a is None or b is None or op is None:
        return json_response(
            {"error": "Expected fields: a, b, op"},
            status="400 Bad Request",
        )

    try:
        a_num = float(a)
        b_num = float(b)
    except (TypeError, ValueError):
        return json_response(
            {"error": "a and b must be numbers"},
            status="400 Bad Request",
        )

    if op == "sum":
        result = a_num + b_num
    elif op == "multiply":
        result = a_num * b_num
    else:
        return json_response(
            {"error": f"Unknown op: {op}"},
            status="400 Bad Request",
        )

    return json_response({"result": result})


@app.route("/ping", methods=["GET", "POST"])
def ping(req):
    if req.method == "GET":
        return {"method": "GET"}

    if req.method == "POST":
        return {"method": "POST"}

    return {"error": "unkown method"}


@app.get("/async")
async def handle_async(req: Request):
    return {"message": "async ok"}


@app.post("/echo")
def echo(request: Request):
    return request.json()


@app.post("/login")
def login(request: Request):
    form = request.form()

    return {"username": form["username"][0]}


@app.get("/ctype")
def content_ctype(request: Request):
    return {"content_type": request.header("content-type")}


@app.get("/test")
def test(a: str, b: str = "B", request: Request | None = None):
    return {
        "a": a,
        "b": b,
        "request_type": type(request).__name__,
    }


# ASGI middleware
app.add_asgi_middleware(LoggingMiddleware)
app.add_asgi_middleware(ServerHeaderMiddleware)

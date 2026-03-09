import datetime as dt

from framework.asgi_app import App
from framework.middleware import logging_middleware, error_middleware
from framework.request import Request
from framework.response import json_response, text_response

app = App()
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
def handle_hello(req: Request):
    name = (req.query.get("name") or ["world"])[0]
    return json_response({"message": f"Hello, {name}!"})


@app.get("/users/<user_id>")
def handle_user(req: Request):
    user_id = req.path_params["user_id"]
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

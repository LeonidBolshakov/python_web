import datetime as dt
import random
from typing import Literal

from pydantic import BaseModel

from framework.depends import Depends
from framework.asgi_app import App
from framework.middleware import (
    error_middleware,
    logging_middleware,
)
from framework.response import json_response, text_response
from framework.types import Request


def get_number():
    return 5


def get_random():
    return random.randint(1, 100)


def get_db():
    print("Вызов get_db")
    return "db"


def get_user(db=Depends(get_db)):
    return f"user_from_{db}"


def get_settings(db=Depends(get_db)):
    return f"settings_from_{db}"


class PydantOp(BaseModel):
    op: Literal["+", "-", "*", "/"]
    a: int | float
    b: int | float


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
def handle_user(user_id: int):
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


@app.post("/sum")
def handle_sum(a: int, b: int) -> int:
    return {"result": a + b}


@app.get("/square")
def square(x: int):
    return {"result": x * x}


@app.get("/flag")
def flag(enabled: bool = False):
    return {"enabled": enabled}


@app.get("/dep")
def dep_test(x: int, num=Depends(get_number)):
    return {"x": x + num}


@app.get("/random")
def random_test(x: int = Depends(get_random)):
    return {"x": x}


@app.get("/test2")
def handler_test2(user=Depends(get_user)):
    return {"user": user}


@app.get("/cache-test")
def cash_test(user=Depends(get_user), settings=Depends(get_settings)):
    return {"user": user, "setting": settings}


@app.post("/pydantic")
def pydantic_test(data: PydantOp):
    if data.op == "+":
        return {"result": data.a + data.b}
    return {"error": f"Для операции '{data.op}' программа разрабатывается"}


def dep():
    print("open")
    try:
        yield "value"
    finally:
        print("close")

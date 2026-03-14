from fastapi import FastAPI
from pydantic import BaseModel


class SumRequest(BaseModel):
    a: int
    b: int


app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}


@app.get("/hello")
def say_hello(name: str = "мир"):
    return {"message": f"Привет, {name}!"}


@app.post("/sum")
def sum_numbers(data: SumRequest):
    return {"result": data.a + data.b}


@app.post("/multiplay")
def sum_numbers(data: SumRequest):
    return {"result": data.a * data.b}

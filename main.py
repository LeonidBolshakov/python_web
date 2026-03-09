from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class SumRequest(BaseModel):
    a: int
    b: int


@app.get("/")
def read_root():
    return {"message": "FastAPI работает!"}


@app.get("/hello")
def say_hello(name: str = "Мир"):
    return {"message": f"Привет, {name}!"}


@app.post("/sum")
def calculate_sum(data: SumRequest):
    return {"result": data.a + data.b}

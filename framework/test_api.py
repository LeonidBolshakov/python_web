import requests

r = requests.post(
    "http://localhost:8000/sum",
    json={"a": 3, "b": 7},
)

print("status:", r.status_code)
print("response:", r.text)

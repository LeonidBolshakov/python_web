import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs
from typing import Any


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes
    path_params: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))


def _get_headers(environ: dict) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").title()
            headers[name] = value

    if "CONTENT_TYPE" in environ:
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if "CONTENT_LENGTH" in environ:
        headers["Content-Length"] = environ["CONTENT_LENGTH"]

    return headers


def _read_body(environ: dict) -> bytes:
    try:
        length_str = environ.get("CONTENT_LENGTH") or "0"
        length = int(length_str)
    except ValueError:
        length = 0

    if length <= 0:
        return b""

    return environ["wsgi.input"].read(length)


def build_request(environ: dict) -> Request:
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"
    query_string = environ.get("QUERY_STRING") or ""
    query = parse_qs(query_string, keep_blank_values=True)
    headers = _get_headers(environ)
    body = _read_body(environ)

    return Request(
        method=method,
        path=path,
        query=query,
        headers=headers,
        body=body,
    )

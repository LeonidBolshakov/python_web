import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Response:
    status: int = 200
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: bytes = b""

    def with_default_headers(self) -> "Response":
        headers = list(self.headers)

        if not any(name.lower() == b"content-type" for name, _ in headers):
            headers.append(
                (
                    b"content-type",
                    b"text/plain; charset=utf-8",
                )
            )

        if not any(name.lower() == b"content-length" for name, _ in headers):
            headers.append(
                (
                    b"content-length",
                    str(len(self.body)).encode(),
                )
            )

        return Response(
            body=self.body,
            status=self.status,
            headers=headers,
        )


def json_response(
    data: Any,
    status: str = "200 OK",
    headers: list[tuple[str, str]] | None = None,
) -> Response:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    result_headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    if headers:
        result_headers.extend(headers)
    return Response(status=status, headers=result_headers, body=payload)


def text_response(
    text: str,
    status: str = "200 OK",
    headers: list[tuple[str, str]] | None = None,
) -> Response:
    payload = text.encode("utf-8")
    result_headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(payload))),
    ]
    if headers:
        result_headers.extend(headers)
    return Response(status=status, headers=result_headers, body=payload)

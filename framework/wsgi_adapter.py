from request import Request
from urllib.parse import parse_qs

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
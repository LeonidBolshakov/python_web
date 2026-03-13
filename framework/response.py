import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Response:
    """
    Простая структура HTTP-ответа для учебного фреймворка.

    * ``status`` — числовой HTTP статус (например, 200 для «OK»).
    * ``headers`` — список пар байтов (имя, значение). Сохраняем заголовки в
      байтовом виде, поскольку ASGI-спецификация требует отправлять заголовки
      как ``bytes``. Для удобства в ваших обработчиках можно передавать
      заголовки как строки, они будут приведены к ``bytes`` в момент
      сериализации (см. ``asgi_app``).
    * ``body`` — полезная нагрузка ответа в виде ``bytes``.

    Метод ``with_default_headers`` гарантирует, что в ответе присутствуют
    заголовки ``content-type`` и ``content-length``, если они ещё не заданы.
    """

    status: int = 200
    headers: list[tuple[bytes, bytes]] = field(default_factory=list)
    body: bytes = b""

    def with_default_headers(self) -> "Response":
        """
        Возвращает новую копию ответа с добавленными заголовками
        ``content-type`` и ``content-length``, если их ещё нет.

        При проверке мы приводим имена заголовков к нижнему регистру и
        интерпретируем их как ``bytes``. Это позволяет одинаково
        поддерживать как байтовые, так и строковые имена заголовков в
        исходном списке.
        """
        headers: list[tuple[bytes, bytes]] = []
        # Копируем существующие заголовки, приводя имена/значения к bytes
        for name, value in self.headers:
            name_b = name if isinstance(name, bytes) else str(name).encode()
            value_b = value if isinstance(value, bytes) else str(value).encode()
            headers.append((name_b, value_b))
        # Проверяем существование заголовков (без учёта регистра)
        names_lower = {name.lower() for name, _ in headers}
        if b"content-type" not in names_lower:
            headers.append((b"content-type", b"text/plain; charset=utf-8"))
        if b"content-length" not in names_lower:
            headers.append((b"content-length", str(len(self.body)).encode()))
        return Response(status=self.status, headers=headers, body=self.body)


def json_response(
    data: Any,
    status: str | int = 200,
    headers: list[tuple[str, str] | tuple[bytes, bytes]] | None = None,
) -> Response:
    """
    Возвращает ``Response`` с JSON-телом и корректными заголовками.

    * ``data`` будет сериализовано с помощью ``json.dumps`` и закодировано
      в UTF-8.
    * ``status`` может быть числом (например, 200) или строкой вида
      ``"200 OK"``. В последнем случае будет извлечён первый числовой
      компонент.
    * ``headers`` позволяет добавить дополнительные заголовки (как строки
      или ``bytes``), которые будут приведены к байтовому виду.
    """
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    # Разбираем статус
    if isinstance(status, str):
        # Берём первую часть до пробела, если она есть
        try:
            status_code = int(status.split()[0])
        except Exception:
            status_code = 200
    else:
        status_code = int(status)
    result_headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(payload)).encode()),
    ]
    if headers:
        for name, value in headers:
            name_b = name if isinstance(name, bytes) else str(name).encode()
            value_b = value if isinstance(value, bytes) else str(value).encode()
            result_headers.append((name_b, value_b))
    return Response(status=status_code, headers=result_headers, body=payload)


def text_response(
    text: str,
    status: str | int = 200,
    headers: list[tuple[str, str] | tuple[bytes, bytes]] | None = None,
) -> Response:
    """
    Возвращает ``Response`` с текстовым телом и корректными заголовками.

    * ``text`` будет закодирован в UTF-8.
    * ``status`` может быть числом (например, 200) или строкой вида
      ``"200 OK"``. В последнем случае будет извлечён первый числовой
      компонент.
    * ``headers`` позволяет добавить дополнительные заголовки (как строки
      или ``bytes``), которые будут приведены к байтовому виду.
    """
    payload = text.encode("utf-8")
    if isinstance(status, str):
        try:
            status_code = int(status.split()[0])
        except Exception:
            status_code = 200
    else:
        status_code = int(status)
    result_headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(payload)).encode()),
    ]
    if headers:
        for name, value in headers:
            name_b = name if isinstance(name, bytes) else str(name).encode()
            value_b = value if isinstance(value, bytes) else str(value).encode()
            result_headers.append((name_b, value_b))
    return Response(status=status_code, headers=result_headers, body=payload)


def ensure_response(result) -> Response:
    if isinstance(result, Response):
        return result

    if isinstance(result, (dict, list)):
        body = json.dumps(result).encode("utf-8")

        return Response(
            body=body,
            headers=[
                (b"content-type", b"application/json"),
            ],
        )

    if isinstance(result, str):
        return Response(
            body=result.encode("utf-8"),
            headers=[
                (b"content-type", b"text/plain; charset=utf-8"),
            ],
        )

    if isinstance(result, bytes):
        return Response(body=result)

    if result is None:
        return Response(body=b"")

    raise TypeError(f"Unsupported response type: {type(result)}")

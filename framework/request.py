from dataclasses import dataclass, field
from typing import Any
import json
from urllib.parse import parse_qs

from framework.exceptions import BadRequest


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: list[tuple[bytes, bytes]]
    body: bytes
    path_params: dict[str, str] = field(default_factory=dict)
    _json_cache: Any = field(default=None, init=False, repr=False)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if self._json_cache is not None:
            return self._json_cache

        if not self.body:
            return None

        try:
            self._json_cache = json.loads(self.body)
        except json.decoder.JSONDecodeError as e:
            raise BadRequest(f"Ошибка в JSON: {e.msg}")

        return self._json_cache

    def form(self) -> dict[str, list[str]]:
        return parse_qs(self.body.decode("utf-8"))

    def header(self, name:str, default: str | None = None) -> str | None:
        name_b = name.lower().encode()

        for key, value in self.headers:
            if key.lower() == name_b:
                return value.decode()
        return default

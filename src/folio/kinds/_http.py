"""``http`` extension kind.

Calls an external HTTP endpoint to fill derived field values. The
transport is injected so tests can swap a deterministic
``StubHTTPTransport`` for the real ``HTTPXTransport`` (mirrors the
``AIClient`` Protocol pattern from ADR-0009).
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol

from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from .._ai_kind import expand_template
from ..derivation import _BaseDerivation
from ..exceptions import FolioError


# --- HTTP Protocol --------------------------------------------------------


@dataclass
class HTTPResponse:
    """Normalized response shape used by the executor."""

    status_code: int
    headers: dict[str, str]
    body: str


class HTTPTransport(Protocol):
    """Minimal interface required by ``execute_http``."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: str | None,
    ) -> HTTPResponse:
        ...


class HTTPXTransport:
    """Adapter that exposes the ``httpx`` library through ``HTTPTransport``."""

    def __init__(self, client: Any | None = None, timeout: float = 30.0) -> None:
        if client is None:
            import httpx

            client = httpx.Client(timeout=timeout)
        self._client = client

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: str | None,
    ) -> HTTPResponse:
        response = self._client.request(
            method=method,
            url=url,
            headers=headers,
            content=content,
        )
        return HTTPResponse(
            status_code=response.status_code,
            headers={k.lower(): v for k, v in response.headers.items()},
            body=response.text,
        )


@dataclass
class _CannedHTTPResponse:
    method: str
    url_substring: str
    response: HTTPResponse


class StubHTTPTransport:
    """Deterministic ``HTTPTransport`` for tests and offline smokes."""

    def __init__(self) -> None:
        self._canned: list[_CannedHTTPResponse] = []
        self.calls: list[dict[str, Any]] = []

    def prepare(
        self,
        *,
        method: str,
        url_substring: str,
        body: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._canned.append(
            _CannedHTTPResponse(
                method=method.upper(),
                url_substring=url_substring,
                response=HTTPResponse(
                    status_code=status_code,
                    headers={k.lower(): v for k, v in (headers or {}).items()},
                    body=body,
                ),
            )
        )

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        content: str | None,
    ) -> HTTPResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "content": content,
            }
        )
        for canned in self._canned:
            if canned.method == method.upper() and canned.url_substring in url:
                return canned.response
        raise FolioError(
            f"StubHTTPTransport has no canned response for {method} {url}"
        )


# --- HTTPDerivation -------------------------------------------------------


class HTTPDerivation(_BaseDerivation):
    """A derivation whose value comes from an HTTP API call."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    kind: Literal["http"]
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    headers: dict[str, str] | None = None
    body_template: str | None = None
    response_path: str | None = None
    response_schema: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_http_invariants(self) -> Self:
        if len(self.targets) >= 2:
            if not self.response_schema:
                raise ValueError(
                    "multi-target http derivation must declare response_schema"
                )
            if set(self.response_schema.keys()) != set(self.targets):
                raise ValueError(
                    "http response_schema keys must equal targets: "
                    f"{sorted(self.response_schema.keys())} vs {sorted(self.targets)}"
                )
        else:
            if self.response_schema is not None:
                raise ValueError(
                    "single-target http derivation must not declare response_schema"
                )
        return self


def execute_http(
    derivation: HTTPDerivation,
    inputs: dict[str, Any],
    *,
    transport: HTTPTransport,
) -> dict[str, Any]:
    """Run the http derivation and return ``{target: value, ...}``."""
    rendered_url = expand_template(derivation.url, inputs)
    rendered_body = (
        expand_template(derivation.body_template, inputs)
        if derivation.body_template is not None
        else None
    )

    response = transport.request(
        method=derivation.method,
        url=rendered_url,
        headers=derivation.headers or {},
        content=rendered_body,
    )

    if not 200 <= response.status_code < 300:
        raise FolioError(
            f"http derivation got status {response.status_code} from {rendered_url}"
        )

    body = _parse_body(response)

    if len(derivation.targets) == 1:
        target = derivation.targets[0]
        if derivation.response_path:
            return {target: _resolve_path(body, derivation.response_path)}
        return {target: body}

    assert derivation.response_schema is not None  # validated by Pydantic
    return {
        target: _resolve_path(body, path)
        for target, path in derivation.response_schema.items()
    }


def _parse_body(response: HTTPResponse) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return _json.loads(response.body)
        except _json.JSONDecodeError as exc:
            raise FolioError(
                f"http response advertised JSON but failed to parse: {exc.msg}"
            ) from exc
    # Best-effort JSON parsing even without the content-type header.
    try:
        return _json.loads(response.body)
    except _json.JSONDecodeError:
        return response.body


def _resolve_path(data: Any, path: str) -> Any:
    """Walk a dot-separated path. Missing segments resolve to ``None``."""
    current = data
    for segment in path.split("."):
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, list):
            try:
                current = current[int(segment)]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return current


__all__ = [
    "HTTPDerivation",
    "HTTPResponse",
    "HTTPTransport",
    "HTTPXTransport",
    "StubHTTPTransport",
    "execute_http",
]

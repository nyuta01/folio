"""Phase 1 ``ai`` kind execution driver.

The driver is decoupled from the Anthropic SDK by an ``AIClient``
Protocol so tests can inject a deterministic stub. The only module that
imports ``anthropic`` is ``AnthropicClientAdapter``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .derivation import AIDerivation
from .exceptions import FolioError


class AIKindError(FolioError):
    """Raised when an ``ai`` kind invocation fails to produce valid output."""


# --- protocol --------------------------------------------------------------


@dataclass
class AIResponse:
    """Normalized response shape used by the driver."""

    text: str
    input_tokens: int
    output_tokens: int


class AIClient(Protocol):
    """Minimal interface required by ``materialize_ai``."""

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
    ) -> AIResponse:
        ...


# --- result ----------------------------------------------------------------


@dataclass
class AIResult:
    """The outcome of one ai-kind invocation."""

    values: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    raw_text: str


# --- price table -----------------------------------------------------------


# Per-million-token rates in USD. Conservative defaults for the Claude 4
# family; unknown models leave ``cost_usd`` as ``None``.
PRICE_TABLE_USD: dict[str, tuple[float, float]] = {
    "claude-opus-4": (15.0, 75.0),
    "claude-opus-4-5": (15.0, 75.0),
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Return cost in USD or ``None`` when the model is not in the table."""
    if model not in PRICE_TABLE_USD:
        return None
    in_rate, out_rate = PRICE_TABLE_USD[model]
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


# --- template expansion ---------------------------------------------------


_TEMPLATE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def expand_template(template: str, inputs: dict[str, Any]) -> str:
    """Expand ``{{ field_name }}`` placeholders only.

    The full Mustache / Jinja2 surfaces are intentionally unsupported per
    §8.2 of the design overview ("language-independent subset").
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in inputs:
            raise AIKindError(f"prompt references unknown field {name!r}")
        return str(inputs[name])

    return _TEMPLATE_PATTERN.sub(replace, template)


# --- driver ----------------------------------------------------------------


def materialize_ai(
    derivation: AIDerivation,
    inputs: dict[str, Any],
    *,
    client: AIClient,
    prompt_body: str | None = None,
    max_tokens: int = 1024,
) -> AIResult:
    """Run one ``ai`` derivation and return the parsed values."""
    body = prompt_body if prompt_body is not None else derivation.prompt
    if body is None:
        raise AIKindError(
            "ai derivation has no prompt; pass prompt_body explicitly when "
            "the source is a prompt_ref"
        )

    rendered = expand_template(body, inputs)
    response = client.messages_create(
        model=derivation.model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": rendered}],
    )

    values = _parse_response_values(derivation, response.text)
    cost = compute_cost(derivation.model, response.input_tokens, response.output_tokens)

    return AIResult(
        values=values,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=cost,
        raw_text=response.text,
    )


def _parse_response_values(
    derivation: AIDerivation,
    text: str,
) -> dict[str, Any]:
    targets = derivation.targets

    if derivation.output == "text":
        if len(targets) != 1:
            raise AIKindError(  # pragma: no cover - guarded by Pydantic
                "text output requires exactly one target"
            )
        return {targets[0]: text.strip()}

    # output == "json"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIKindError(f"invalid JSON in response: {exc.msg}") from exc

    if len(targets) == 1:
        return {targets[0]: data}

    if not isinstance(data, dict):
        raise AIKindError(
            "multi-target ai derivation expects a JSON object response, "
            f"got {type(data).__name__}"
        )

    missing = [target for target in targets if target not in data]
    if missing:
        raise AIKindError(f"response is missing targets: {sorted(missing)}")

    return {target: data[target] for target in targets}


# --- adapters --------------------------------------------------------------


class AnthropicClientAdapter:
    """Adapter that exposes the Anthropic SDK through the ``AIClient`` Protocol.

    Only this class imports ``anthropic`` so the rest of the module stays
    SDK-agnostic and unit-testable without a network round trip.
    """

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()
        self._client = client

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
    ) -> AIResponse:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        text = "".join(
            getattr(block, "text", "") for block in response.content
        )
        usage = getattr(response, "usage", None)
        return AIResponse(
            text=text,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )


@dataclass
class _CannedResponse:
    """A canned response keyed by a substring of the rendered prompt."""

    prompt_substring: str
    text: str
    input_tokens: int = 10
    output_tokens: int = 10


class StubAIClient:
    """Deterministic ``AIClient`` for tests and offline materialize.

    Either register canned responses with :meth:`prepare` or pass a
    ``responder(rendered_prompt) -> str`` callable. The stub records every
    call for assertions.
    """

    def __init__(
        self,
        responder: Callable[[str], str] | None = None,
    ) -> None:
        self._canned: list[_CannedResponse] = []
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def prepare(
        self,
        prompt_substring: str,
        text: str,
        *,
        input_tokens: int = 10,
        output_tokens: int = 10,
    ) -> None:
        self._canned.append(
            _CannedResponse(
                prompt_substring=prompt_substring,
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
    ) -> AIResponse:
        rendered = messages[-1]["content"] if messages else ""
        self.calls.append(
            {"model": model, "max_tokens": max_tokens, "messages": messages}
        )

        for canned in self._canned:
            if canned.prompt_substring in rendered:
                return AIResponse(
                    text=canned.text,
                    input_tokens=canned.input_tokens,
                    output_tokens=canned.output_tokens,
                )

        if self._responder is not None:
            return AIResponse(
                text=self._responder(rendered),
                input_tokens=10,
                output_tokens=10,
            )

        raise AIKindError(
            f"StubAIClient has no canned response for prompt: {rendered[:80]!r}"
        )


__all__ = [
    "AIClient",
    "AIKindError",
    "AIResponse",
    "AIResult",
    "AnthropicClientAdapter",
    "PRICE_TABLE_USD",
    "StubAIClient",
    "compute_cost",
    "expand_template",
    "materialize_ai",
]

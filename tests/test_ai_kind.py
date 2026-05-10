"""Tests for ``folio._ai_kind`` (Phase 1 ai-kind driver, stub-based)."""

from __future__ import annotations

import pytest

from folio._ai_kind import (
    AIKindError,
    StubAIClient,
    compute_cost,
    expand_template,
    materialize_ai,
)
from folio.derivation import AIDerivation


def _ai(
    *,
    targets: list[str] | None = None,
    output: str = "text",
    output_schema: dict[str, str] | None = None,
    prompt: str = "Industry of {{ company_name }}.",
    inputs: list[str] | None = None,
    model: str = "claude-sonnet-4-6",
) -> AIDerivation:
    return AIDerivation.model_validate(
        {
            "targets": targets or ["industry_tag"],
            "inputs": inputs or ["company_name"],
            "kind": "ai",
            "model": model,
            "prompt": prompt,
            "output": output,
            **({"output_schema": output_schema} if output_schema else {}),
        }
    )


# --- expand_template -------------------------------------------------------


def test_expand_template_simple() -> None:
    result = expand_template(
        "Industry of {{ company_name }}.",
        {"company_name": "Acme"},
    )
    assert result == "Industry of Acme."


def test_expand_template_multiple_fields() -> None:
    result = expand_template(
        "{{ a }} & {{ b }} = {{ a }}{{ b }}",
        {"a": "1", "b": "2"},
    )
    assert result == "1 & 2 = 12"


def test_expand_template_strips_whitespace_in_braces() -> None:
    assert expand_template("Hello {{name}}", {"name": "X"}) == "Hello X"
    assert expand_template("Hello {{  name  }}", {"name": "X"}) == "Hello X"


def test_expand_template_missing_field_rejected() -> None:
    with pytest.raises(AIKindError, match="unknown field 'missing'"):
        expand_template("Hi {{ missing }}", {"a": "1"})


# --- text output -----------------------------------------------------------


def test_text_output_single_target() -> None:
    derivation = _ai()
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing\n")

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.values == {"industry_tag": "Manufacturing"}
    assert result.input_tokens == 10
    assert result.output_tokens == 10


def test_text_output_strips_leading_and_trailing_whitespace() -> None:
    derivation = _ai()
    client = StubAIClient()
    client.prepare("Industry of Acme", "   Manufacturing   ")

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.values == {"industry_tag": "Manufacturing"}


# --- json output (single target) ------------------------------------------


def test_json_output_single_target_returns_parsed_value() -> None:
    derivation = _ai(targets=["tags"], output="json")
    client = StubAIClient()
    client.prepare("Industry of", '["a", "b", "c"]')

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.values == {"tags": ["a", "b", "c"]}


# --- json output (multi target) -------------------------------------------


def test_json_output_multi_target_returns_dict() -> None:
    derivation = _ai(
        targets=["industry_tag", "hq_country"],
        output="json",
        output_schema={"industry_tag": "string", "hq_country": "string"},
    )
    client = StubAIClient()
    client.prepare(
        "Industry of",
        '{"industry_tag": "Software", "hq_country": "United States"}',
    )

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.values == {
        "industry_tag": "Software",
        "hq_country": "United States",
    }


def test_json_output_multi_target_missing_field_rejected() -> None:
    derivation = _ai(
        targets=["a", "b"],
        output="json",
        output_schema={"a": "string", "b": "string"},
    )
    client = StubAIClient()
    client.prepare("Industry of", '{"a": "1"}')

    with pytest.raises(AIKindError, match="missing targets"):
        materialize_ai(derivation, {"company_name": "Acme"}, client=client)


def test_json_output_multi_target_non_object_rejected() -> None:
    derivation = _ai(
        targets=["a", "b"],
        output="json",
        output_schema={"a": "string", "b": "string"},
    )
    client = StubAIClient()
    client.prepare("Industry of", "[1, 2]")

    with pytest.raises(AIKindError, match="expects a JSON object"):
        materialize_ai(derivation, {"company_name": "Acme"}, client=client)


def test_json_output_invalid_json_rejected() -> None:
    derivation = _ai(targets=["tags"], output="json")
    client = StubAIClient()
    client.prepare("Industry of", "not-json{")

    with pytest.raises(AIKindError, match="invalid JSON"):
        materialize_ai(derivation, {"company_name": "Acme"}, client=client)


# --- cost calculation ------------------------------------------------------


@pytest.mark.parametrize(
    "model,input_tokens,output_tokens,expected",
    [
        ("claude-sonnet-4-6", 1000, 500, (1000 * 3.0 + 500 * 15.0) / 1_000_000),
        ("claude-opus-4-7", 100, 50, (100 * 15.0 + 50 * 75.0) / 1_000_000),
        ("claude-haiku-4-5", 2000, 1000, (2000 * 1.0 + 1000 * 5.0) / 1_000_000),
    ],
)
def test_compute_cost_known_models(
    model: str,
    input_tokens: int,
    output_tokens: int,
    expected: float,
) -> None:
    assert compute_cost(model, input_tokens, output_tokens) == pytest.approx(
        expected
    )


def test_compute_cost_unknown_model_returns_none() -> None:
    assert compute_cost("not-a-model", 1000, 500) is None


def test_materialize_ai_records_cost_for_known_model() -> None:
    derivation = _ai(model="claude-sonnet-4-6")
    client = StubAIClient()
    client.prepare(
        "Industry of",
        "Software",
        input_tokens=1000,
        output_tokens=500,
    )

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.cost_usd == pytest.approx(
        (1000 * 3.0 + 500 * 15.0) / 1_000_000.0
    )


def test_materialize_ai_returns_none_cost_for_unknown_model() -> None:
    derivation = _ai(model="not-a-model")
    client = StubAIClient()
    client.prepare("Industry of", "Software")

    result = materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert result.cost_usd is None


# --- prompt body override --------------------------------------------------


def test_prompt_body_override_used_when_passed() -> None:
    derivation = _ai(prompt="default")
    client = StubAIClient()
    client.prepare("override", "OK")

    result = materialize_ai(
        derivation,
        {"company_name": "ignored"},
        client=client,
        prompt_body="override prompt body",
    )

    assert result.values == {"industry_tag": "OK"}


# --- stub diagnostics ------------------------------------------------------


def test_stub_records_calls() -> None:
    derivation = _ai()
    client = StubAIClient()
    client.prepare("Industry of Acme", "Manufacturing")

    materialize_ai(derivation, {"company_name": "Acme"}, client=client)

    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "claude-sonnet-4-6"


def test_stub_falls_back_to_responder_callable() -> None:
    derivation = _ai()
    captured: list[str] = []

    def responder(rendered: str) -> str:
        captured.append(rendered)
        return "FromCallable"

    client = StubAIClient(responder=responder)
    result = materialize_ai(
        derivation, {"company_name": "Beta"}, client=client
    )

    assert result.values == {"industry_tag": "FromCallable"}
    assert "Beta" in captured[0]


def test_stub_raises_when_no_match_and_no_responder() -> None:
    derivation = _ai()
    client = StubAIClient()
    with pytest.raises(AIKindError, match="no canned response"):
        materialize_ai(derivation, {"company_name": "Z"}, client=client)

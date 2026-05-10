"""Tests for ``folio._cache`` (Phase 1 input_hash + cache filesystem)."""

from __future__ import annotations

from pathlib import Path

import pytest

from folio._cache import (
    CACHE_PREFIX,
    cache_path,
    compute_input_hash,
    default_cache_root,
    read_cache,
    sha256_file,
    sha256_hex,
    write_cache,
)
from folio.derivation import AIDerivation, ImportDerivation


def _ai(prompt: str = "Industry of {{ company_name }}") -> AIDerivation:
    return AIDerivation.model_validate(
        {
            "targets": ["industry_tag"],
            "inputs": ["company_name"],
            "kind": "ai",
            "model": "claude-sonnet-4-6",
            "prompt": prompt,
            "output": "text",
        }
    )


def _import() -> ImportDerivation:
    return ImportDerivation.model_validate(
        {
            "targets": ["legacy_id"],
            "kind": "import",
            "source": "refs/legacy.csv",
            "key_field": "id",
            "value_field": "legacy_customer_id",
        }
    )


# --- sha256 helpers --------------------------------------------------------


def test_sha256_hex_matches_known_value() -> None:
    # echo -n "" | shasum -a 256 → e3b0c44...
    assert sha256_hex(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_file_streams_large_payload(tmp_path: Path) -> None:
    path = tmp_path / "blob.bin"
    payload = b"abc" * 100_000
    path.write_bytes(payload)
    assert sha256_file(path) == sha256_hex(payload)


# --- compute_input_hash ----------------------------------------------------


def test_input_hash_for_ai_is_deterministic() -> None:
    derivation = _ai()
    h1 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        prompt_body="Industry of {{ company_name }}",
        inputs={"company_name": "Acme"},
    )
    h2 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        prompt_body="Industry of {{ company_name }}",
        inputs={"company_name": "Acme"},
    )
    assert h1 == h2
    assert h1.startswith(CACHE_PREFIX)


def test_input_hash_independent_of_input_dict_order() -> None:
    derivation = _ai()
    h1 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        prompt_body="x",
        inputs={"a": 1, "b": 2},
    )
    h2 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        prompt_body="x",
        inputs={"b": 2, "a": 1},
    )
    assert h1 == h2


@pytest.mark.parametrize(
    "field,override",
    [
        ("derivation_file_hash", {"derivation_file_hash": "bbb"}),
        ("prompt_body", {"prompt_body": "Different prompt"}),
        ("inputs", {"inputs": {"company_name": "DataFlow"}}),
        ("model", "swap_model"),
    ],
)
def test_input_hash_changes_when_any_component_changes(
    field: str, override: object
) -> None:
    derivation = _ai()
    base = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        prompt_body="Industry of {{ company_name }}",
        inputs={"company_name": "Acme"},
    )

    if field == "model":
        mutated = AIDerivation.model_validate(
            {
                "targets": ["industry_tag"],
                "inputs": ["company_name"],
                "kind": "ai",
                "model": "claude-sonnet-4-7",
                "prompt": "Industry of {{ company_name }}",
                "output": "text",
            }
        )
        new_hash = compute_input_hash(
            mutated,
            derivation_file_hash="aaa",
            prompt_body="Industry of {{ company_name }}",
            inputs={"company_name": "Acme"},
        )
    else:
        kwargs = {
            "derivation_file_hash": "aaa",
            "prompt_body": "Industry of {{ company_name }}",
            "inputs": {"company_name": "Acme"},
        }
        kwargs.update(override)  # type: ignore[arg-type]
        new_hash = compute_input_hash(derivation, **kwargs)  # type: ignore[arg-type]

    assert base != new_hash


def test_input_hash_for_ai_requires_prompt_body() -> None:
    with pytest.raises(ValueError, match="prompt_body"):
        compute_input_hash(
            _ai(),
            derivation_file_hash="aaa",
            inputs={"company_name": "Acme"},
        )


def test_input_hash_for_import_requires_source_file_hash() -> None:
    with pytest.raises(ValueError, match="source_file_hash"):
        compute_input_hash(
            _import(),
            derivation_file_hash="aaa",
            inputs={"id": "cust_001"},
        )


def test_input_hash_for_import_changes_with_source_hash() -> None:
    derivation = _import()
    h1 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        source_file_hash="src1",
        inputs={"id": "cust_001"},
    )
    h2 = compute_input_hash(
        derivation,
        derivation_file_hash="aaa",
        source_file_hash="src2",
        inputs={"id": "cust_001"},
    )
    assert h1 != h2


# --- cache filesystem ------------------------------------------------------


def test_cache_round_trip(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    payload = {"value": "Manufacturing", "cost_usd": 0.0008}
    input_hash = "sha256:" + ("a" * 64)

    write_cache(cache_root, input_hash, payload)
    assert read_cache(cache_root, input_hash) == payload


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    assert read_cache(tmp_path / "cache", "sha256:" + ("0" * 64)) is None


def test_cache_path_uses_two_char_shard(tmp_path: Path) -> None:
    digest = "sha256:" + "abcdef" + ("1" * 58)
    path = cache_path(tmp_path / "cache", digest)
    parts = path.relative_to(tmp_path / "cache").parts
    assert parts[0] == "ab"
    assert parts[1].endswith(".json")


def test_cache_path_rejects_non_hex(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="hex SHA-256"):
        cache_path(tmp_path / "cache", "sha256:zz")


def test_cache_path_rejects_missing_prefix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must start with"):
        cache_path(tmp_path / "cache", "abc" * 21 + "a")


def test_default_cache_root_lives_outside_repo(tmp_path: Path) -> None:
    """Cache root must not nest under the sample sheet directory (ADR-0008)."""
    repo_root = Path(__file__).resolve().parents[1]
    cache_root = default_cache_root("test-sheet")
    # Resolved cache root should not be under any folder inside the repo.
    assert "folio" in str(cache_root)
    assert "test-sheet" in str(cache_root)
    try:
        cache_root.relative_to(repo_root)
    except ValueError:
        return  # Outside the repo as expected.
    pytest.fail(f"default_cache_root must live outside the repo, got {cache_root}")

"""Phase 1 ``input_hash`` and cache filesystem helpers.

Cache key per §11 of the design overview:

```
input_hash = sha256(canonical_json({
  derivation_file_hash: <SHA-256 of derivations/<name>.yaml>,
  prompt_file_hash:     <SHA-256 of prompt body>,  # only ai
  model:                <model id>,                 # only ai
  source_file_hash:     <SHA-256 of source file>,   # only import
  inputs:               { <input_field>: <input_value>, ... },
}))
```

`canonical_json` follows RFC 8785 (JCS, JSON Canonicalization Scheme).
The cache root lives outside any sheet (ADR-0008) at
``<user-cache>/folio/<sheet-id>/cache/`` resolved via ``platformdirs``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import platformdirs
import rfc8785

from .derivation import AIDerivation, Derivation, ImportDerivation


CACHE_PREFIX = "sha256:"


# --- hashing ---------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    """Return the hex SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of ``path`` streamed in 64 KiB chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_input_hash(
    derivation: Any,
    *,
    derivation_file_hash: str,
    inputs: dict[str, Any],
    prompt_body: str | None = None,
    source_file_hash: str | None = None,
    extra_components: dict[str, Any] | None = None,
) -> str:
    """Compute the ``input_hash`` cache key for one record × derivation.

    Returns ``sha256:<hex>``. The canonical form is RFC 8785 JSON over
    a payload tailored to the derivation kind. Extension kinds pass
    their kind-specific payload through ``extra_components``.
    """
    payload: dict[str, Any] = {
        "derivation_file_hash": derivation_file_hash,
        "inputs": inputs,
    }
    if isinstance(derivation, AIDerivation):
        if prompt_body is None:
            raise ValueError(
                "compute_input_hash for ai derivation requires prompt_body"
            )
        payload["prompt_file_hash"] = sha256_hex(prompt_body.encode("utf-8"))
        payload["model"] = derivation.model
    elif isinstance(derivation, ImportDerivation):
        if source_file_hash is None:
            raise ValueError(
                "compute_input_hash for import derivation requires source_file_hash"
            )
        payload["source_file_hash"] = source_file_hash
    # Extension kinds (sql, http, ...) populate via extra_components.

    if extra_components:
        payload.update(extra_components)

    canonical = rfc8785.dumps(payload)
    return CACHE_PREFIX + sha256_hex(canonical)


# --- cache filesystem ------------------------------------------------------


def default_cache_root(sheet_id: str) -> Path:
    """Return ``<user-cache>/folio/<sheet-id>/cache/`` (per ADR-0008)."""
    user_cache = Path(platformdirs.user_cache_dir("folio"))
    return user_cache / sheet_id / "cache"


def cache_path(cache_root: Path, input_hash: str) -> Path:
    """Resolve ``cache_root / <digest[:2]> / <digest>.json`` for an input_hash."""
    digest = _strip_prefix(input_hash)
    return Path(cache_root) / digest[:2] / f"{digest}.json"


def read_cache(cache_root: Path, input_hash: str) -> dict[str, Any] | None:
    """Return the cached payload for ``input_hash`` or ``None`` on miss."""
    path = cache_path(cache_root, input_hash)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def write_cache(
    cache_root: Path,
    input_hash: str,
    value: dict[str, Any],
) -> None:
    """Persist ``value`` to the cache directory under ``input_hash``."""
    path = cache_path(cache_root, input_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


# --- internal --------------------------------------------------------------


def _strip_prefix(input_hash: str) -> str:
    if not input_hash.startswith(CACHE_PREFIX):
        raise ValueError(
            f"input_hash must start with {CACHE_PREFIX!r}; got {input_hash!r}"
        )
    digest = input_hash[len(CACHE_PREFIX):]
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"input_hash must be a hex SHA-256 digest; got {input_hash!r}")
    return digest


__all__ = [
    "CACHE_PREFIX",
    "cache_path",
    "compute_input_hash",
    "default_cache_root",
    "read_cache",
    "sha256_file",
    "sha256_hex",
    "write_cache",
]

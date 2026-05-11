"""Folio: portable, AI-native data sheets.

Phase 0 surface: ``contract.yaml`` loading and validation, plus the six
core operations on a ``Sheet``. See ``docs/design-docs/overview.md`` for the
full specification.
"""

from .contract import (
    Contract,
    LogicalType,
    Property,
    Schema,
    load_contract,
)
from .derivation import (
    AIDerivation,
    Derivation,
    DerivationError,
    ImportDerivation,
    MaterializationConfig,
    detect_cycles,
    load_derivation,
    load_derivations,
    topological_sort,
)
from ._skill import (
    Skill,
    SkillArgument,
    export_claude_skills,
    load_skills,
    validate_skills_manifest,
)
from .exceptions import (
    ContractError,
    FolioError,
    LockTimeoutError,
    OperationError,
    PermissionDeniedError,
    QueryError,
    RecordsError,
    SheetError,
    SkillError,
)
from .readme import Frontmatter, ReadmeError, load_readme_metadata, parse_frontmatter
from .scripts import ScriptError, ScriptResult, discover_scripts
from .sheet import Sheet, open_sheet

__all__ = [
    "AIDerivation",
    "Contract",
    "ContractError",
    "Derivation",
    "DerivationError",
    "FolioError",
    "Frontmatter",
    "ImportDerivation",
    "LockTimeoutError",
    "LogicalType",
    "MaterializationConfig",
    "OperationError",
    "PermissionDeniedError",
    "Property",
    "QueryError",
    "ReadmeError",
    "RecordsError",
    "Schema",
    "ScriptError",
    "ScriptResult",
    "Sheet",
    "SheetError",
    "Skill",
    "SkillArgument",
    "SkillError",
    "detect_cycles",
    "discover_scripts",
    "export_claude_skills",
    "load_contract",
    "load_derivation",
    "load_derivations",
    "load_readme_metadata",
    "load_skills",
    "open_sheet",
    "parse_frontmatter",
    "topological_sort",
    "validate_skills_manifest",
]

__version__ = "0.1.0"

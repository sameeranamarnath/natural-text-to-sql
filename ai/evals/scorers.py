"""Deterministic scorers for text-to-SQL output.

These run offline with no model and no database, which is what lets them gate
every pull request cheaply. Model-graded scoring lives in `judge.py` and runs on
demand, calibrated against this rubric rather than replacing it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardrails import is_read_only_sql

EVALS_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = EVALS_DIR / "golden.jsonl"

_TABLE_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_CTE_DEF = re.compile(r"\bwith\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    reference_sql: str
    tables: tuple[str, ...] = ()
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Case:
        return cls(
            id=str(raw["id"]),
            question=str(raw["question"]),
            reference_sql=str(raw.get("reference_sql", "")),
            tables=tuple(raw.get("tables", ())),
            must_contain=tuple(raw.get("must_contain", ())),
            must_not_contain=tuple(raw.get("must_not_contain", ())),
        )


@dataclass
class Score:
    case_id: str
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())

    @property
    def failures(self) -> list[str]:
        return sorted(name for name, ok in self.checks.items() if not ok)


def load_dataset(path: Path | None = None) -> list[Case]:
    """Read the golden dataset (JSON Lines). One case per line keeps diffs readable."""
    target = path or DEFAULT_DATASET
    cases = [
        Case.from_dict(json.loads(line))
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id in golden dataset")
    return cases


def normalise(sql: str) -> str:
    return " ".join(sql.lower().split())


def extract_tables(sql: str) -> set[str]:
    """Referenced tables, with CTE names removed so `with x as (...)` is not counted as a table."""
    referenced = {m.group(1).lower() for m in _TABLE_REF.finditer(sql)}
    ctes = {m.group(1).lower() for m in _CTE_DEF.finditer(sql)}
    return referenced - ctes


def score(case: Case, sql: str) -> Score:
    """Score one candidate statement against a case.

    Functional checks first (correctness), then the non-functional ones
    (read-only, no forbidden tokens) - a wrong-but-safe query and a correct-but-
    destructive one fail for different reasons and should be told apart.
    """
    flat = normalise(sql)
    checks: dict[str, bool] = {
        "read_only": is_read_only_sql(sql),
        "required_phrases": all(p.lower() in flat for p in case.must_contain),
        "forbidden_phrases": not any(p.lower() in flat for p in case.must_not_contain),
    }
    if case.tables:
        checks["known_tables_only"] = extract_tables(sql).issubset({t.lower() for t in case.tables})
    return Score(case_id=case.id, checks=checks)

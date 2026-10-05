"""Unit tests for the eval scorers and the shipped golden dataset."""

from __future__ import annotations

import pytest

from evals.run import run_offline
from evals.scorers import Case, extract_tables, load_dataset, normalise, score


class TestLoadDataset:
    def test_loads_the_shipped_dataset(self) -> None:
        assert len(load_dataset()) == 10

    def test_case_ids_are_unique(self) -> None:
        ids = [c.id for c in load_dataset()]
        assert len(ids) == len(set(ids))

    def test_every_case_has_a_question_and_reference(self) -> None:
        for case in load_dataset():
            assert case.question.strip()
            assert case.reference_sql.strip()

    def test_rejects_duplicate_ids(self, tmp_path: pytest.TempPathFactory) -> None:
        path = tmp_path / "dup.jsonl"  # type: ignore[operator]
        path.write_text(
            '{"id":"a","question":"q","reference_sql":"select 1"}\n'
            '{"id":"a","question":"q","reference_sql":"select 1"}\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="duplicate case id"):
            load_dataset(path)


class TestNormalise:
    def test_collapses_whitespace_and_case(self) -> None:
        assert normalise("SELECT\n  *   FROM   films") == "select * from films"


class TestExtractTables:
    def test_finds_from_and_join_targets(self) -> None:
        sql = "select f.title from films f join ratings r on r.film_id = f.id"
        assert extract_tables(sql) == {"films", "ratings"}

    def test_is_case_insensitive(self) -> None:
        assert extract_tables("SELECT * FROM Films") == {"films"}

    def test_cte_names_are_not_tables(self) -> None:
        sql = "with recent as (select 1) select * from films"
        assert extract_tables(sql) == {"films"}

    def test_no_tables_returns_empty(self) -> None:
        assert extract_tables("select 1") == set()


class TestScore:
    def _case(self, **overrides: object) -> Case:
        base = {
            "id": "c",
            "question": "q",
            "reference_sql": "select count(*) from films",
            "tables": ("films",),
            "must_contain": ("count(",),
            "must_not_contain": ("delete",),
        }
        base.update(overrides)
        return Case(**base)  # type: ignore[arg-type]

    def test_a_correct_statement_passes(self) -> None:
        result = score(self._case(), "select count(*) from films")
        assert result.passed
        assert result.failures == []

    def test_write_statement_fails_read_only(self) -> None:
        result = score(self._case(), "delete from films")
        assert not result.passed
        assert "read_only" in result.failures

    def test_missing_required_phrase_fails(self) -> None:
        result = score(self._case(), "select title from films")
        assert "required_phrases" in result.failures

    def test_forbidden_phrase_fails(self) -> None:
        case = self._case(must_not_contain=("limit",))
        assert "forbidden_phrases" in score(case, "select * from films limit 1").failures

    def test_unknown_table_fails(self) -> None:
        result = score(self._case(), "select count(*) from secret_table")
        assert "known_tables_only" in result.failures

    def test_known_tables_check_is_skipped_when_unscoped(self) -> None:
        case = self._case(tables=())
        assert "known_tables_only" not in score(case, "select * from anything").checks

    def test_failures_are_sorted(self) -> None:
        result = score(self._case(), "delete from secret_table")
        assert result.failures == sorted(result.failures)


class TestShippedGoldenSet:
    """The rubric must accept its own reference answers, or it is wrong."""

    def test_every_reference_statement_passes(self) -> None:
        bad = [c.id for c in load_dataset() if not score(c, c.reference_sql).passed]
        assert bad == []

    def test_offline_runner_returns_success(self) -> None:
        assert run_offline(load_dataset()) == 0

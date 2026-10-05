# Contributing

Thanks for looking. This is a small project with a deliberately strict bar, so
the conventions below are enforced rather than suggested.

## Getting set up

The agent service is self-contained under `ai/`.

```bash
cd ai
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the fast checks - this is the same set CI runs:

```bash
ruff check .
ruff format --check .
pytest
python -m evals.run
```

No model, database or vector store is needed for any of those. Live evals and the
graph itself need vLLM and Qdrant; see `ai/README.md` and `docker-compose.ai.yml`.

## Conventions

**Commits** follow [Conventional Commits](https://www.conventionalcommits.org):
`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`, `refactor:`, `perf:`.
The subject is imperative, lower case, and under 72 characters. The body explains
*why*, not *what* - the diff already shows what.

Example:

```
fix: reject stacked statements in the read-only gate

A trailing "; --" let a second statement through the token check. The gate now
looks for the comment marker as well.
```

**Python** targets 3.11+, is formatted by `ruff format`, and is linted with the
rule set selected in `ai/pyproject.toml`. Type hints are required on public
functions.

**Safety code is standard-library only.** `guardrails.py`, `costs.py` and
`observability.py` must keep importing cleanly with no third-party packages -
that is what lets the safety rules be unit-tested in milliseconds and reused
outside this service. Heavy imports (LangGraph, Qdrant, an HTTP client) stay in
`graph.py`, `store.py` and `main.py`.

**Tests describe behaviour, not implementation.** Name them after the rule they
protect (`test_rejects_blank_input`, not `test_validate`). If a case documents a
known limitation, say so in the docstring - see `test_unquoted_keyword_is_flagged`.

## Changing behaviour

- **Prompt or graph change** - add or update a case in `ai/evals/golden.jsonl`
  first, confirm it fails, then make it pass. That ordering is the point of the
  dataset.
- **Model or provider change** - record the eval delta in the pull request. A
  cheaper model that drops the pass rate is not an improvement.
- **New guardrail** - add the rule, add a test, and add a mention in the README
  threat-model table.

## Reporting a problem

Bugs and questions are welcome as issues. Security issues should not be filed as
issues - see [SECURITY.md](SECURITY.md).

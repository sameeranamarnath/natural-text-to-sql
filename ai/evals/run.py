"""Eval runner for the SQL agent.

    python -m evals.run           # offline rubric self-test (no model, no database)
    python -m evals.run --live    # run the agent and score its output

Offline mode gates every pull request. Live mode is the release gate: it needs
vLLM and Qdrant reachable, so it runs on demand rather than on every commit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.scorers import Case, load_dataset, score


def run_offline(cases: list[Case]) -> int:
    """Score each case's own reference SQL.

    If the rubric rejects its own reference answers then the rubric is wrong, so
    this is a self-test that has to pass before a model is invited in at all.
    """
    failures = 0
    for case in cases:
        result = score(case, case.reference_sql)
        if result.passed:
            print(f"ok    {case.id}")
            continue
        failures += 1
        print(f"FAIL  {case.id}: {', '.join(result.failures)}")
    print(f"\n{len(cases) - failures}/{len(cases)} reference statements pass the rubric")
    return 1 if failures else 0


def run_live(cases: list[Case]) -> int:
    """Run the agent for real and score what it produces."""
    try:
        from graph import ask
    except Exception as exc:  # pragma: no cover - needs the optional service deps
        print(f"live evals need the service dependencies installed: {exc}")
        return 2

    passed = 0
    for case in cases:
        state = ask(case.question)
        result = score(case, state.get("sql", ""))
        passed += int(result.passed)
        marker = "ok  " if result.passed else "FAIL"
        print(f"{marker} {case.id} (repairs={state.get('attempts', 0)})")
        if not result.passed:
            print(f"       {', '.join(result.failures)}")
            print(f"       sql: {state.get('sql', '')}")
    print(f"\npass rate: {passed}/{len(cases)}")
    return 0 if passed == len(cases) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the text-to-SQL evals.")
    parser.add_argument("--live", action="store_true", help="run the agent, not only the rubric")
    parser.add_argument("--dataset", type=Path, default=None, help="path to a golden JSONL file")
    args = parser.parse_args(argv)

    cases = load_dataset(args.dataset)
    if not cases:
        print("no cases loaded")
        return 2
    return run_live(cases) if args.live else run_offline(cases)


if __name__ == "__main__":
    raise SystemExit(main())

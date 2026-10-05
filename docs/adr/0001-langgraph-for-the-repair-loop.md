# 1. Use LangGraph for the SQL repair loop

- **Date:** 2026-10-05
- **Status:** Accepted

## Context

Text-to-SQL fails often enough on real schemas that a single model call is not a
shippable design. The usual failure is not a wrong answer but an *unexecutable*
one: a column that does not exist, a function the dialect lacks, a join key
guessed wrong. Those are recoverable, and the database says exactly what is
wrong - but only if something is there to read that message and try again.

The retry also has to be bounded. An unbounded retry loop against a paid model is
a cost incident waiting to happen.

## Decision

Model the task as an explicit state machine with LangGraph, and put the retry
inside it:

```
retrieve_schema -> draft_sql -> validate_sql --> run_sql --> summarise -> END
                                     |               |
                                     +--> repair_sql <+
                                          (capped)
```

The failing statement and the database's own error text are fed back to the
model. Attempts are capped by `MAX_REPAIR_ATTEMPTS`; the conditional edges decide
between `run`, `repair` and `stop`.

## Consequences

- The control flow lives in the repository rather than inside prompt text, so it
  can be reasoned about, reviewed and traced node by node.
- Each node is independently testable, and the graph itself can be inspected.
- The common failure modes recover without human involvement.
- Cost rises with retries, which is exactly why the cap and the per-request cost
  meter (`costs.py`) were added together rather than separately.

## Alternatives considered

- **One large prompt that says "make sure the SQL is valid."** Rejected: it turns
  a loop into a hope, and there is nowhere to put a cap.
- **A LangChain agent with a SQL tool.** Rejected: the tool executes as soon as it
  is called, so a validation gate has nowhere to sit.
- **A hand-rolled `while` loop.** Genuinely viable - a graph compiles down to
  something similar. Rejected because the graph's streaming and tracing hooks are
  what make a run observable, and that is most of the value here.

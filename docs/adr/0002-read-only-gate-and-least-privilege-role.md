# 2. Read-only gate in code, least-privilege role in the database

- **Date:** 2026-10-05
- **Status:** Accepted

## Context

The service turns untrusted natural language into SQL and executes it. A model
can be talked into emitting `DROP TABLE`, and an injection payload can arrive
through retrieved content as easily as through the user's message.

There are two ways to stop that: inspect the SQL before running it, or remove the
privilege to run it in the first place.

## Decision

Do both, and be explicit about which one is load-bearing.

1. **In application code** - `guardrails.is_read_only_sql` accepts only a single
   `SELECT`/`WITH` statement and rejects any statement containing DDL/DML tokens.
   It is cheap, standard-library only, and returns an error the repair loop can
   act on.
2. **In the database** - connect as a role holding only `SELECT`. This is the
   control that actually matters.

The gate is documented as a gate, not a sandbox. Its known limitations are pinned
by tests so nobody mistakes it for a parser:

- it tokenises on whitespace, so an unquoted keyword used as an identifier is a
  false positive (`test_unquoted_keyword_is_flagged`);
- a quoted literal does not trip it (`test_quoted_literals_do_not_trip_the_gate`);
- it does not understand SQL grammar, so it cannot reason about what a statement
  will actually do.

## Consequences

- The common case is caught early with a useful message, before any query runs.
- A bypass of the gate is still stopped by the database role.
- Reviewers must not treat the regex as the security boundary. That expectation
  is written down here precisely so it does not have to be argued again.

## Alternatives considered

- **A full parser (sqlglot) for the gate.** Rejected for now: it would cut false
  positives, but it adds a dependency to a module that is deliberately
  standard-library only, and it still would not replace the database role.
  Worth revisiting if false positives become a practical problem.
- **Regex only, no role.** Rejected. Regex-based SQL inspection is a well-known
  losing game.
- **A read replica.** Complementary, not a substitute - a replica is not a
  permission boundary, and on some engines it still accepts DDL.

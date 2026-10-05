# Security

## Reporting a vulnerability

Report privately through GitHub Security Advisories (Security tab -> "Report a
vulnerability"). Please do not open a public issue.

Include what you did, what happened, what you expected, and the commit you
tested. Expect an acknowledgement within 72 hours and an assessment within a
week.

## Threat model

This service accepts untrusted natural-language input and turns it into SQL that
runs against a database. The threats below are in scope, and each has a control
that can be pointed at:

| Threat | Control | Where |
| --- | --- | --- |
| Destructive SQL | read-only gate: a single SELECT/WITH, DDL/DML tokens rejected | `ai/guardrails.py` |
| Prompt injection ("ignore previous instructions") | pattern screening, fails closed | `ai/guardrails.py` |
| Credentials or PII reaching prompts, vectors or logs | redaction of emails, phone numbers, card-like numbers, cloud access keys and bearer tokens | `ai/guardrails.py` |
| Runaway model spend | per-request token metering plus an optional budget ceiling | `ai/costs.py` |
| Credential exposure | every secret is read from the environment; `.env` is git-ignored | `ai/config.py` |

Explicitly **out of scope**, and worth stating plainly:

- **The read-only gate is a gate, not a sandbox.** The real control is a
  least-privilege database role holding only `SELECT`. Do not rely on the regex.
- **Injection screening is heuristic.** It narrows the attack surface; it does
  not close it. Retrieved content is untrusted input too.
- **The schema in Qdrant is not a boundary.** Access control belongs at the
  database, not at retrieval.

See `docs/adr/0002-read-only-gate-and-least-privilege-role.md` for why the
defence is layered this way.

## Handling secrets

Never commit `.env`. If a credential is committed, treat it as compromised:
**rotate it first**, then remove it from the tree. Deleting the file without
rotating the secret fixes nothing, because history keeps a copy.

## Supported versions

`main` is the supported version.

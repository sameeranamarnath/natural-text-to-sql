"""LangGraph agent that turns a question into a validated, executed SQL query.

    retrieve_schema -> draft_sql -> validate_sql -+-> run_sql -------> summarise -> END
                                                   |
                                                   +-> repair_sql -> validate_sql (capped loop)

The repair loop is the point of the design. Single-shot text-to-SQL fails often
enough on real schemas that feeding the database's own error message back into
the model, with an attempt cap, beats reaching for a larger model.
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import create_engine, inspect, text

from config import get_settings
from llm import chat_model
from store import search

READ_ONLY_PREFIXES = ("select", "with")
FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter", "create", "grant",
    "revoke", "truncate", "attach", "detach", "pragma", "vacuum",
)


class SqlState(TypedDict, total=False):
    question: str
    schema_context: list[dict[str, Any]]
    sql: str
    error: str | None
    attempts: int
    rows: list[dict[str, Any]]
    answer: str


def _clean(raw: str) -> str:
    """Strip markdown fences and stray prefixes the model likes to add."""
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        s = parts[1] if len(parts) > 1 else s
        if s.lower().startswith("sql"):
            s = s[3:]
    return s.strip().rstrip(";")


def _is_read_only(sql: str) -> bool:
    words = " ".join(sql.split()).lower().split()
    if not words or words[0] not in READ_ONLY_PREFIXES:
        return False
    return not any(w in FORBIDDEN for w in words)


def collect_schema_chunks() -> list[str]:
    """One chunk per table, so retrieval can pull only the tables a question needs."""
    engine = create_engine(get_settings().database_url)
    inspector = inspect(engine)
    chunks: list[str] = []
    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        ddl = ", ".join(f"{c['name']} {c['type']}" for c in columns)
        chunks.append(f"TABLE {table}({ddl})")
    return chunks


def retrieve_schema(state: SqlState) -> dict[str, Any]:
    return {"schema_context": search(state["question"])}


def draft_sql(state: SqlState) -> dict[str, Any]:
    context = "\n\n".join(h.get("text", "") for h in state.get("schema_context", []))
    prompt = (
        "You write SQL. Use only the tables and columns listed below.\n"
        "Reply with a single read-only SELECT statement and no commentary.\n\n"
        f"Schema:\n{context}\n\nQuestion: {state['question']}\nSQL:"
    )
    raw = chat_model().invoke(prompt).content
    return {"sql": _clean(str(raw)), "attempts": 0, "error": None}


def validate_sql(state: SqlState) -> dict[str, Any]:
    sql = state.get("sql", "")
    if not sql:
        return {"error": "The model returned an empty statement."}
    if not _is_read_only(sql):
        return {"error": "Rejected: not a single read-only SELECT/WITH statement."}
    return {"error": None}


def run_sql(state: SqlState) -> dict[str, Any]:
    s = get_settings()
    try:
        engine = create_engine(s.database_url)
        with engine.connect() as conn:
            result = conn.execute(text(state["sql"]))
            rows = [dict(r._mapping) for r in result.fetchmany(s.row_limit)]
        return {"rows": rows, "error": None}
    except Exception as exc:  # surface the database's own words to the repair step
        return {"rows": [], "error": f"{type(exc).__name__}: {exc}"}


def repair_sql(state: SqlState) -> dict[str, Any]:
    context = "\n\n".join(h.get("text", "") for h in state.get("schema_context", []))
    prompt = (
        "This SQL failed. Fix it and reply with the corrected statement only.\n\n"
        f"Schema:\n{context}\n\nQuestion: {state['question']}\n"
        f"Failing SQL:\n{state['sql']}\nDatabase error:\n{state['error']}\n"
        f"Attempt {state.get('attempts', 0) + 1}:"
    )
    raw = chat_model(temperature=0.1).invoke(prompt).content
    return {"sql": _clean(str(raw)), "attempts": state.get("attempts", 0) + 1, "error": None}


def summarise(state: SqlState) -> dict[str, Any]:
    if state.get("error") and not state.get("rows"):
        return {"answer": f"No runnable query after retries. Last error: {state['error']}"}
    prompt = (
        "Answer the question in one or two sentences using only these rows.\n\n"
        f"Question: {state['question']}\nSQL: {state['sql']}\nRows: {state.get('rows', [])[:10]}"
    )
    return {"answer": str(chat_model().invoke(prompt).content).strip()}


def _after_validate(state: SqlState) -> Literal["run", "repair", "stop"]:
    if not state.get("error"):
        return "run"
    if state.get("attempts", 0) >= get_settings().max_repair_attempts:
        return "stop"
    return "repair"


def _after_run(state: SqlState) -> Literal["repair", "summarise"]:
    if state.get("error") and state.get("attempts", 0) < get_settings().max_repair_attempts:
        return "repair"
    return "summarise"


def build_graph():
    g = StateGraph(SqlState)
    g.add_node("retrieve_schema", retrieve_schema)
    g.add_node("draft_sql", draft_sql)
    g.add_node("validate_sql", validate_sql)
    g.add_node("run_sql", run_sql)
    g.add_node("repair_sql", repair_sql)
    g.add_node("summarise", summarise)

    g.add_edge(START, "retrieve_schema")
    g.add_edge("retrieve_schema", "draft_sql")
    g.add_edge("draft_sql", "validate_sql")
    g.add_conditional_edges(
        "validate_sql",
        _after_validate,
        {"run": "run_sql", "repair": "repair_sql", "stop": "summarise"},
    )
    g.add_conditional_edges(
        "run_sql", _after_run, {"repair": "repair_sql", "summarise": "summarise"}
    )
    g.add_edge("repair_sql", "validate_sql")
    g.add_edge("summarise", END)
    return g.compile()


APP = build_graph()


def ask(question: str) -> SqlState:
    return APP.invoke({"question": question, "attempts": 0})

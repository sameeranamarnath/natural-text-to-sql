"""HTTP surface for the SQL agent.

    uvicorn main:api --host 0.0.0.0 --port 8080

Endpoints:
    GET  /health   - liveness plus the resolved model/collection names
    POST /ingest   - read the target schema and load it into Qdrant
    POST /ask      - run the agent; streams graph progress over SSE
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import get_settings
from costs import UsageMeter, estimate_cost_usd
from graph import APP, ask, collect_schema_chunks
from guardrails import redact, screen_injection, validate_question
from observability import configure, span
from store import search, upsert_chunks

api = FastAPI(title="text-to-sql agent", version="1.0.0")

# Process-local spend tracker. In a multi-replica deployment this is the piece
# that moves to a shared store or an OTLP counter; here it keeps the contract
# visible: every request reports what it cost.
METER = UsageMeter()
configure("sql-agent")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class IngestResponse(BaseModel):
    indexed: int


@api.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "llm_model": s.llm_model,
        "embed_model": s.embed_model,
        "collection": s.qdrant_collection,
    }


@api.post("/ingest", response_model=IngestResponse)
def ingest() -> IngestResponse:
    """Load the target schema into Qdrant so retrieval has something to hit."""
    chunks = collect_schema_chunks()
    if not chunks:
        return IngestResponse(indexed=0)
    count = upsert_chunks(chunks, [{"source": "schema"} for _ in chunks])
    return IngestResponse(indexed=count)


def screen_question(question: str) -> dict[str, Any] | None:
    """Structural checks first, then injection screening.

    Fails closed on purpose: a rejected request is cheaper to explain than a
    successful one that quietly ignored its instructions.
    """
    shape = validate_question(question)
    if not shape.ok:
        return {"error": "invalid_question", "reasons": list(shape.reasons)}
    injection = screen_injection(question)
    if not injection.ok:
        return {"error": "possible_prompt_injection", "reasons": list(injection.reasons)}
    return None


@api.post("/ask")
def ask_endpoint(req: AskRequest) -> dict[str, Any]:
    problem = screen_question(req.question)
    if problem is not None:
        raise HTTPException(status_code=400, detail=problem)

    # Redacted before the question reaches the model or the vector store.
    question, redacted_kinds = redact(req.question)

    with span("agent.ask") as record:
        result = ask(question)
        record.attributes["agent.attempts"] = result.get("attempts", 0)

    model = get_settings().llm_model
    usage = result.get("usage", [])
    for call in usage:
        METER.record(model, call["prompt_tokens"], call["completion_tokens"])
    request_cost = sum(
        estimate_cost_usd(model, c["prompt_tokens"], c["completion_tokens"]) for c in usage
    )

    return {
        "answer": result.get("answer", ""),
        "sql": result.get("sql", ""),
        "rows": result.get("rows", []),
        "attempts": result.get("attempts", 0),
        "error": result.get("error"),
        "redacted": list(redacted_kinds),
        "cost_usd": round(request_cost, 6),
    }


@api.get("/usage")
def usage() -> dict[str, Any]:
    """Cumulative spend for this process, against the optional budget ceiling."""
    return METER.summary()


@api.post("/ask/stream")
async def ask_stream(req: AskRequest) -> StreamingResponse:
    """Emit each graph node as it finishes, then the final answer.

    Uses LangGraph's stream so the UI can show the draft/repair steps instead of
    a spinner for the whole traversal.
    """

    async def events() -> AsyncIterator[str]:
        state: dict[str, Any] = {"question": req.question, "attempts": 0}
        for step in APP.stream(state):
            for node, update in step.items():
                payload = json.dumps({"node": node, "update": _safe(update)})
                yield f"event: node\ndata: {payload}\n\n"
                state.update(update)
        yield f"event: done\ndata: {json.dumps(_safe(state))}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def _safe(d: dict[str, Any]) -> dict[str, Any]:
    """Keep SSE payloads small - full retrieval hits are noise for the client."""
    out = dict(d)
    if "schema_context" in out:
        out["schema_context"] = [h.get("text", "")[:200] for h in out["schema_context"]]
    if "rows" in out:
        out["rows"] = out["rows"][:10]
    return out


@api.get("/search")
def quick_search(q: str) -> dict[str, Any]:
    """Debug helper: what retrieval returns for a question, before any generation."""
    return {"hits": search(q)}

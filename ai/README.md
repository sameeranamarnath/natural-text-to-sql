# SQL agent service

Agentic layer alongside the original single-shot `text-to-sql.py`. A LangGraph
state machine retrieves the relevant schema, drafts SQL, validates it, runs it,
and repairs itself from the database's own error messages.

## Graph

```
retrieve_schema -> draft_sql -> validate_sql --> run_sql --> summarise -> END
                                     |               |
                                     +--> repair_sql <+
                                        (capped retries)
```

| Node | What it does |
| --- | --- |
| `retrieve_schema` | Qdrant vector search over schema chunks - only relevant tables reach the prompt |
| `draft_sql` | vLLM generates a candidate statement |
| `validate_sql` | read-only guard: single SELECT/WITH, no DDL/DML keywords |
| `run_sql` | executes with a row cap and captures the raw database error |
| `repair_sql` | feeds the failing SQL plus the error back to the model |
| `summarise` | answers the original question from the returned rows |

## Stack

- LangGraph for orchestration
- vLLM serving `Qwen/Qwen3-32B` (chat) and `BAAI/bge-m3` (embeddings) over the OpenAI API
- Qdrant for schema retrieval
- FastAPI + SSE for the HTTP surface

## Run

Whole stack:

```
docker compose -f ../docker-compose.ai.yml up
```

Against an existing vLLM and Qdrant:

```
pip install -r requirements.txt
export LLM_BASE_URL=https://<your-endpoint>/v1
export QDRANT_URL=http://localhost:6333
uvicorn main:api --port 8080
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | liveness and resolved model names |
| `POST` | `/ingest` | read the schema from `DATABASE_URL` and load it into Qdrant |
| `POST` | `/ask` | run the agent; returns answer, SQL and rows |
| `POST` | `/ask/stream` | same, as SSE with one event per graph node |
| `GET` | `/search?q=` | retrieval-only debug view |

## Configuration

Set through the environment (see `config.py`): `LLM_BASE_URL`, `LLM_MODEL`,
`EMBED_BASE_URL`, `EMBED_MODEL`, `QDRANT_URL`, `QDRANT_COLLECTION`,
`DATABASE_URL`, `MAX_REPAIR_ATTEMPTS`, `RETRIEVAL_TOP_K`.

## Note

vLLM wants a GPU. On CPU-only or serverless, point `LLM_BASE_URL` at a hosted
OpenAI-compatible endpoint and drop the `vllm` services from the compose file.

# natural-text-to-sql

Turn a plain-English question into SQL, run it against a database, and show the
result - no hand-written query. Built on LangChain + GPT-3.5/4 with a Streamlit
front end.

## What it does

- Reads the database schema and hands it to the model
- Converts the natural-language question into SQL
- Executes that SQL against the configured SQLAlchemy URI
- Streamlit UI takes the question, an optional URI, and the API key

## Stack

- Python, LangChain, OpenAI (GPT-3.5/4)
- Streamlit for the UI
- Any SQLAlchemy-compatible database

## Databases it has been run against

- `imdb-movie.sqlite` (SQLite) - the Kaggle IMDB export
- A hosted PostgreSQL (Neon) import of the OMDb dataset
- Anything else with a SQLAlchemy URI

## Setup

```
pip install -r requirements.txt --user
```

Create a `.env` with:

```
omdb_url=postgresql+psycopg2://<user>:<password>@<host>/omdb?sslmode=require
OPENAI_API_KEY=your-key
```

`omdb_url` is only used when you do not paste a URI into the UI.

## Run

```
streamlit run text-to-sql.py --server.enableCORS false --server.enableXsrfProtection false
```

## Notes

- A `gpt4free` path is included as a no-key fallback; it is noticeably slower.
- A local quantized LLaMA + NSQL attempt is also in the file tree - the output was
  not reliable enough to use, so OpenAI stays the default.
- Credentials come from the environment; nothing is hardcoded.

## Agent service (`ai/`)

`text-to-sql.py` is the original single-shot version. `ai/` reimplements the same
job as a LangGraph agent with a self-correcting loop:

```
retrieve_schema -> draft_sql -> validate_sql --> run_sql --> summarise -> END
                                     |               |
                                     +--> repair_sql <+
                                        (capped retries)
```

- **Retrieval** - schema chunks live in Qdrant, so only the relevant tables reach the prompt
- **Models** - vLLM serving an OpenAI-compatible API (`Qwen/Qwen3-32B` for chat, `BAAI/bge-m3` for embeddings)
- **Guard** - only a single read-only `SELECT`/`WITH` statement is allowed through
- **Repair** - a failed query is fed back with the database's own error message, up to `MAX_REPAIR_ATTEMPTS`

```
docker compose -f docker-compose.ai.yml up
```

`POST /ingest` loads the schema, `POST /ask` returns answer + SQL + rows, and
`POST /ask/stream` emits one SSE event per graph node. See [`ai/README.md`](ai/README.md).

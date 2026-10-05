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

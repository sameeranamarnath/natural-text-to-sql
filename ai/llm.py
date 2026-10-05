"""Model clients.

Both factories return LangChain objects wired to the vLLM OpenAI-compatible
endpoint, so swapping to a hosted provider is a URL change, not a code change.
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from config import get_settings


def chat_model(temperature: float | None = None, max_tokens: int = 2048) -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        temperature=s.llm_temperature if temperature is None else temperature,
        max_tokens=max_tokens,
        max_retries=2,
        timeout=120,
    )


def embed_model() -> OpenAIEmbeddings:
    s = get_settings()
    # vLLM ignores the key, but the OpenAI client requires a non-empty string.
    return OpenAIEmbeddings(
        model=s.embed_model,
        base_url=s.embed_base_url,
        api_key=s.llm_api_key,
        check_embedding_ctx_length=False,
    )

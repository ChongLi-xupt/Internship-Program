"""
LLM abstraction layer — unified interface to multiple LLM providers.

Supports OpenAI (and any OpenAI-compatible endpoint), DeepSeek, Anthropic,
and Ollama (local/private deployment).

All LLM calls go through this layer — never import provider SDKs directly
in business logic.

IMPORTANT — chat and embedding are decoupled on purpose.
Several chat providers (DeepSeek in particular) expose NO embedding endpoint,
so the embedding provider is resolved from its own EMBEDDING_* settings and
never inherits the chat provider's base_url.
"""

import asyncio
import os
from abc import ABC, abstractmethod
from threading import Lock
from typing import List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

from app.config import settings


class LLMProvider(ABC):
    """Abstract LLM provider."""

    @abstractmethod
    def get_chat_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        """Get a chat model instance."""
        ...


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    def get_embeddings(self) -> Embeddings:
        """Get an embeddings model instance."""

    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        model = self.get_embeddings()
        return await model.aembed_query(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents (batch)."""
        model = self.get_embeddings()
        return await model.aembed_documents(texts)


class OpenAILLMProvider(LLMProvider):
    """OpenAI-compatible LLM provider (works with Azure, local proxies, etc.)."""

    def get_chat_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or settings.openai_model,
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_base_url,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 4096),
            streaming=kwargs.get("streaming", False),
        )


class DeepSeekLLMProvider(LLMProvider):
    """
    DeepSeek LLM provider.

    DeepSeek speaks the OpenAI protocol, so we reuse ChatOpenAI with a custom
    base_url instead of pulling in another SDK.

    Model notes:
      * deepseek-chat     — V3 series, fast, supports temperature /
                            max_tokens / response_format={"type":"json_object"}.
                            This is the default for every node.
      * deepseek-reasoner — R1 series. Ignores temperature/top_p, emits a
                            long reasoning trace before the answer and has a
                            much higher first-token latency. Do NOT use it on
                            latency-sensitive paths (query_rewrite,
                            intent_recognize). It is only worth it for
                            sql_compile on genuinely hard multi-table joins.
    """

    #: Models that silently ignore sampling params — we strip them to avoid
    #: 400s on stricter gateways that proxy DeepSeek.
    _NO_SAMPLING_MODELS = ("deepseek-reasoner",)

    def get_chat_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        model_name = model or settings.deepseek_model

        params: dict = {
            "model": model_name,
            "openai_api_key": settings.deepseek_api_key,
            "openai_api_base": settings.deepseek_base_url,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "streaming": kwargs.get("streaming", False),
        }

        if not any(m in model_name for m in self._NO_SAMPLING_MODELS):
            params["temperature"] = kwargs.get("temperature", 0.1)

        # Opt-in JSON mode. Callers that parse structured output should pass
        # json_mode=True AND keep the word "json" in the prompt — DeepSeek
        # rejects the request otherwise.
        if kwargs.get("json_mode"):
            params["model_kwargs"] = {"response_format": {"type": "json_object"}}

        return ChatOpenAI(**params)


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def get_chat_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 4096),
        )


class OllamaLLMProvider(LLMProvider):
    """Ollama local LLM provider (for private deployment)."""

    def get_chat_model(self, model: str | None = None, **kwargs) -> BaseChatModel:
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model or settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=kwargs.get("temperature", 0.1),
        )


def _resolve_embedding_endpoint() -> tuple[str, str]:
    """
    Resolve (api_key, base_url) for the embedding service.

    Falls back to the OpenAI chat credentials only when EMBEDDING_* is unset,
    which keeps single-vendor setups (pure OpenAI) working with zero config.
    """
    api_key = settings.embedding_api_key or settings.openai_api_key
    base_url = settings.embedding_base_url or settings.openai_base_url
    return api_key, base_url


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider for OpenAI and any OpenAI-compatible endpoint
    (SiliconFlow, DashScope compatible-mode, Zhipu, vLLM, Xinference, ...).
    """

    def get_embeddings(self) -> Embeddings:
        from langchain_openai import OpenAIEmbeddings

        api_key, base_url = _resolve_embedding_endpoint()

        params: dict = {
            "model": settings.embedding_model,
            "openai_api_key": api_key,
            "openai_api_base": base_url,
            "chunk_size": settings.embedding_batch_size,
        }

        # `dimensions` is an OpenAI v3-only knob. BGE / Qwen / Zhipu models
        # served through compatible gateways will 400 on it.
        if settings.embedding_send_dimensions:
            params["dimensions"] = settings.embedding_dimensions

        return OpenAIEmbeddings(**params)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider — fully offline, no API cost."""

    def get_embeddings(self) -> Embeddings:
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )


# ──────────────────────────────────────────────────────────────────────────
# Local sentence-transformers embedding
# ──────────────────────────────────────────────────────────────────────────

_st_model = None          # loaded SentenceTransformer, process-wide singleton
_st_model_lock = Lock()   # guards the (slow, ~GB) first load against races


def _resolve_hf_device() -> str:
    """Explicit device wins; otherwise prefer CUDA when torch reports it."""
    if settings.hf_embedding_device:
        return settings.hf_embedding_device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # torch missing or broken CUDA build
        pass
    return "cpu"


def _load_sentence_transformer():
    """
    Load the local model exactly once per process.

    Loading is deliberately eager-but-cached rather than per-call: the base
    EmbeddingProvider calls get_embeddings() on *every* embed operation, and
    re-reading a multi-GB checkpoint each time would be catastrophic.
    """
    global _st_model
    if _st_model is not None:
        return _st_model

    with _st_model_lock:
        if _st_model is not None:  # another thread won the race
            return _st_model

        if settings.hf_embedding_offline:
            # Fail fast on a cache miss instead of silently hitting the network.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "EMBEDDING_PROVIDER=huggingface requires sentence-transformers. "
                "Install it with:  pip install sentence-transformers"
            ) from exc

        if settings.hf_embedding_torch_threads > 0:
            try:
                import torch

                torch.set_num_threads(settings.hf_embedding_torch_threads)
            except Exception:
                pass

        model_id = settings.hf_embedding_model or settings.embedding_model
        device = _resolve_hf_device()

        try:
            model = SentenceTransformer(model_id, device=device)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load local embedding model {model_id!r} on {device!r}. "
                f"When HF_EMBEDDING_OFFLINE=true the model must already exist in "
                f"the local HuggingFace cache (~/.cache/huggingface/hub). "
                f"Original error: {exc}"
            ) from exc

        _st_model = model
        return _st_model


class _SentenceTransformerEmbeddings(Embeddings):
    """
    LangChain Embeddings adapter over a local sentence-transformers model.

    Implemented directly rather than via langchain-huggingface so that the
    asymmetric BGE query instruction is applied on the query side only —
    embedding documents with the instruction prefix degrades retrieval.
    """

    def _encode(self, texts: List[str]) -> List[List[float]]:
        model = _load_sentence_transformer()
        vectors = model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            normalize_embeddings=settings.hf_embedding_normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._encode(list(texts))

    def embed_query(self, text: str) -> List[float]:
        prefix = settings.hf_embedding_query_instruction or ""
        return self._encode([prefix + text])[0]

    # Encoding is CPU/GPU-bound and blocking. Offload it so a batch import
    # cannot stall the FastAPI event loop.
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_documents, list(texts)
        )

    async def aembed_query(self, text: str) -> List[float]:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_query, text
        )


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """
    Fully local embedding provider backed by sentence-transformers.

    No API key, no network, no per-token cost. The model is loaded once and
    shared process-wide.
    """

    _adapter = _SentenceTransformerEmbeddings()

    def get_embeddings(self) -> Embeddings:
        return self._adapter

    @staticmethod
    def probe_dimensions() -> int:
        """Actual output width of the loaded model — used by startup checks."""
        model = _load_sentence_transformer()
        return int(model.get_sentence_embedding_dimension())


# Provider instances cache
_llm_provider: LLMProvider | None = None
_embedding_provider: EmbeddingProvider | None = None

_LLM_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAILLMProvider,
    "deepseek": DeepSeekLLMProvider,
    "anthropic": AnthropicLLMProvider,
    "ollama": OllamaLLMProvider,
}

_EMBEDDING_PROVIDERS: dict[str, type[EmbeddingProvider]] = {
    "openai": OpenAIEmbeddingProvider,
    "huggingface": HuggingFaceEmbeddingProvider,
    "hf": HuggingFaceEmbeddingProvider,  # alias
    "local": HuggingFaceEmbeddingProvider,  # alias
    "ollama": OllamaEmbeddingProvider,
}


def _get_llm_provider() -> LLMProvider:
    global _llm_provider
    if _llm_provider is None:
        p = settings.llm_provider.lower()
        cls = _LLM_PROVIDERS.get(p)
        if cls is None:
            raise ValueError(
                f"Unsupported LLM provider: {p!r}. "
                f"Expected one of: {', '.join(_LLM_PROVIDERS)}"
            )
        _llm_provider = cls()
    return _llm_provider


def get_llm(model: str | None = None, **kwargs) -> BaseChatModel:
    """Get a chat model instance using the configured provider."""
    return _get_llm_provider().get_chat_model(model, **kwargs)


def get_light_llm(**kwargs) -> BaseChatModel:
    """
    Cheaper/faster model for low-stakes nodes (intent classification,
    query rewrite). Falls back to the main model when no light model is set.
    """
    p = settings.llm_provider.lower()
    light = {
        "openai": settings.openai_light_model,
        "deepseek": settings.deepseek_light_model,
    }.get(p)
    return get_llm(model=light or None, **kwargs)


def get_embedding_provider() -> EmbeddingProvider:
    global _embedding_provider
    if _embedding_provider is None:
        ep = settings.embedding_provider.lower()
        cls = _EMBEDDING_PROVIDERS.get(ep)
        if cls is None:
            raise ValueError(
                f"Unsupported embedding provider: {ep!r}. "
                f"Expected one of: {', '.join(_EMBEDDING_PROVIDERS)}"
            )
        _embedding_provider = cls()
    return _embedding_provider


def validate_llm_config() -> list[str]:
    """
    Startup sanity check. Returns a list of human-readable problems;
    empty list means the config is coherent.

    Catches the single most common misconfiguration: pointing the whole app
    at DeepSeek and forgetting that it cannot produce embeddings.
    """
    problems: list[str] = []
    p = settings.llm_provider.lower()

    ep = settings.embedding_provider.lower()
    local_embedding = ep in ("huggingface", "hf", "local", "ollama")

    if p == "deepseek":
        if not settings.deepseek_api_key:
            problems.append("LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is empty.")
        emb_key, emb_url = _resolve_embedding_endpoint()
        if ep == "openai":
            if "deepseek.com" in emb_url:
                problems.append(
                    "EMBEDDING base_url points at DeepSeek, which has no "
                    "/embeddings endpoint. Set EMBEDDING_BASE_URL to a real "
                    "embedding service (e.g. SiliconFlow), or run embeddings "
                    "locally with EMBEDDING_PROVIDER=huggingface."
                )
            if not emb_key:
                problems.append(
                    "No embedding credentials. Set EMBEDDING_API_KEY "
                    "(DeepSeek keys do not work for embeddings), or switch to "
                    "EMBEDDING_PROVIDER=huggingface for a fully local model."
                )
    elif p == "openai" and not settings.openai_api_key:
        problems.append("LLM_PROVIDER=openai but OPENAI_API_KEY is empty.")
    elif p == "anthropic" and not settings.anthropic_api_key:
        problems.append("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty.")

    # --- local embedding specific checks ---
    if ep in ("huggingface", "hf", "local"):
        model_id = settings.hf_embedding_model or settings.embedding_model
        if not model_id:
            problems.append(
                "EMBEDDING_PROVIDER=huggingface but no model set. "
                "Set HF_EMBEDDING_MODEL (e.g. BAAI/bge-large-zh-v1.5)."
            )
        if model_id.startswith("text-embedding-"):
            problems.append(
                f"EMBEDDING_PROVIDER=huggingface but the model is {model_id!r}, "
                f"which is an OpenAI API model with no local weights. "
                f"Set HF_EMBEDDING_MODEL to a sentence-transformers model."
            )
        if settings.embedding_send_dimensions:
            problems.append(
                "EMBEDDING_SEND_DIMENSIONS=true has no effect for local models "
                "and signals a copy-paste from an OpenAI config. Set it to false."
            )

    # Dimension mismatch silently corrupts the vector index — the store is
    # created with EMBEDDING_DIMENSIONS and rejects everything else later.
    if local_embedding and settings.embedding_dimensions == 1536:
        problems.append(
            "EMBEDDING_DIMENSIONS is still 1536 (the OpenAI default) while a "
            "local embedding model is configured. Set it to the model's real "
            "width (bge-large-zh-v1.5 => 1024, bge-m3 => 1024, "
            "MiniLM-L12-v2 => 384) BEFORE indexing any document."
        )

    return problems

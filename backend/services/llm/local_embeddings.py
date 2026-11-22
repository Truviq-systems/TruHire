"""
Local, self-contained embedding generation via `fastembed` (Qdrant's own ONNX-based
embedding library). No external API key, no DGX/vLLM dependency — runs entirely inside
this process on CPU. Used when EMBEDDING_PROVIDER=local.
"""
import threading
from typing import List

from backend.config import settings

_model = None
# The startup warm-up thread and the first search request can both ask for the model while it is
# still loading. Without a lock each builds its own copy (double the RAM on a small host, often
# an out-of-memory kill) and the search times out. With it, the second caller waits for the first.
_load_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _load_lock:
            if _model is None:
                from fastembed import TextEmbedding
                kwargs = {"cache_dir": settings.FASTEMBED_CACHE_DIR} if settings.FASTEMBED_CACHE_DIR else {}
                _model = TextEmbedding(model_name=settings.LOCAL_EMBEDDING_MODEL, **kwargs)
    return _model


def is_ready() -> bool:
    """True once the model is loaded in this process (a search no longer pays the cold start)."""
    return _model is not None


def generate_embedding(text: str) -> List[float]:
    if not text:
        raise ValueError("Cannot generate an embedding from empty text.")
    model = _get_model()
    vector = next(iter(model.embed([text])))
    return [float(x) for x in vector]


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Embed many texts in one fastembed call. fastembed batches internally and is
    meaningfully faster per-item this way than one generate_embedding() call per text -
    the throughput path used by bulk ingestion."""
    if not texts:
        return []
    model = _get_model()
    return [[float(x) for x in vector] for vector in model.embed(texts)]

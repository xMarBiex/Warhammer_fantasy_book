"""Wspólny loader embeddingów (fastembed, model wielojęzyczny E5-large).

Model pobierany jest z Google Cloud Storage (bucket qdrant-fastembed), bo
HuggingFace jest w tym środowisku zablokowany. Po pobraniu ładowany lokalnie
przez `specific_model_path`, co całkowicie pomija HF.

Dla E5 wymagane są prefiksy: "passage: " (dokumenty) i "query: " (zapytania).
"""
import os

from fastembed import TextEmbedding
from fastembed.common.model_management import ModelManagement

MODEL_NAME = "intfloat/multilingual-e5-large"
GCS_URL = "https://storage.googleapis.com/qdrant-fastembed/fast-multilingual-e5-large.tar.gz"
CACHE_DIR = os.environ.get("FASTEMBED_CACHE", ".cache/fastembed")
_MODEL_SUBDIR = "fast-multilingual-e5-large"


def ensure_model():
    """Zwraca ścieżkę do lokalnego modelu; pobiera z GCS jeśli brak."""
    path = os.path.join(CACHE_DIR, _MODEL_SUBDIR)
    if os.path.exists(os.path.join(path, "model.onnx")):
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    return str(ModelManagement.retrieve_model_gcs(
        MODEL_NAME, GCS_URL, CACHE_DIR, deprecated_tar_struct=True))


def load_embedder():
    path = ensure_model()
    return TextEmbedding(MODEL_NAME, specific_model_path=path)


def embed_passages(model, texts, batch_size=32):
    return model.embed(["passage: " + t for t in texts], batch_size=batch_size)


def embed_query(model, text):
    return next(iter(model.embed(["query: " + text])))

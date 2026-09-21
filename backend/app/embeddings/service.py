"""Embedding service abstraction with dimension validation and batching."""

from app.core.config import get_settings
from app.core.exceptions import VectorDimensionMismatchError
from app.core.logging import logger

settings = get_settings()


class EmbeddingService:
    """Provides dense vector embeddings with strict dimension validation."""

    def __init__(
        self,
        model_name: str | None = None,
        expected_dimension: int | None = None,
        device: str | None = None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.expected_dimension = expected_dimension or settings.EMBEDDING_DIMENSION
        self.device = device or settings.EMBEDDING_DEVICE
        self._model = None

    def _get_model(self):
        """Lazy load sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model '{self.model_name}' on {self.device}...")
                self._model = SentenceTransformer(self.model_name, device=self.device)
            except Exception as e:
                logger.error(f"Failed to load embedding model {self.model_name}: {e}")
                raise RuntimeError(f"Could not load embedding model: {e}")
        return self._model

    def validate_dimension(self, vector: list[float]) -> None:
        """Validate embedding dimension against expected dimension."""
        actual_dim = len(vector)
        if actual_dim != self.expected_dimension:
            raise VectorDimensionMismatchError(expected=self.expected_dimension, actual=actual_dim)

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        model = self._get_model()
        cleaned_text = text.replace("\n", " ").strip()
        vector = model.encode(cleaned_text, normalize_embeddings=True).tolist()
        self.validate_dimension(vector)
        return vector

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for a list of document chunks in batches."""
        if not texts:
            return []

        model = self._get_model()
        cleaned_texts = [t.replace("\n", " ").strip() for t in texts]
        vectors = model.encode(
            cleaned_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

        for vec in vectors:
            self.validate_dimension(vec)

        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding vector for search queries."""
        # Preprocessing query for retrieval if needed
        return self.embed_text(query)

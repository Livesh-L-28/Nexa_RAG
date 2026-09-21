"""Cross-encoder reranking layer for candidate refinement."""

from app.core.config import get_settings
from app.core.logging import logger
from app.retrieval.vector_search import ScoredChunk

settings = get_settings()


class CrossEncoderReranker:
    """Reranks candidate chunks using a lightweight HuggingFace CrossEncoder model."""

    def __init__(
        self,
        model_name: str | None = None,
        enabled: bool | None = None,
    ):
        self.model_name = model_name or settings.RERANKER_MODEL_NAME
        self.enabled = enabled if enabled is not None else settings.RERANKING_ENABLED
        self._model = None

    def _get_model(self):
        """Lazy-load the CrossEncoder model."""
        if self._model is None and self.enabled:
            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading CrossEncoder model '{self.model_name}'...")
                self._model = CrossEncoder(self.model_name)
            except Exception as e:
                logger.warning(
                    f"Could not load CrossEncoder model '{self.model_name}': {e}. Disabling reranker."
                )
                self.enabled = False
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[ScoredChunk],
        top_k: int | None = None,
    ) -> list[ScoredChunk]:
        """Rerank candidates using CrossEncoder. Returns top_k reranked chunks."""
        k = top_k or settings.TOP_K
        if not candidates:
            return []

        # If reranking is disabled or only 1 candidate, return as is
        if not self.enabled or len(candidates) <= 1:
            return candidates[:k]

        model = self._get_model()
        if model is None:
            return candidates[:k]

        try:
            # Pair query with each candidate chunk content
            pairs = [[query, c.content] for c in candidates]
            cross_scores = model.predict(pairs)

            reranked: list[ScoredChunk] = []
            for i, c in enumerate(candidates):
                raw_score = float(cross_scores[i])
                # Convert logits to probability score if needed, or record raw score
                c.metadata["initial_score"] = c.score
                c.metadata["reranker_score"] = raw_score
                c.score = raw_score
                reranked.append(c)

            reranked.sort(key=lambda x: x.score, reverse=True)
            return reranked[:k]
        except Exception as e:
            logger.error(f"Error during reranking: {e}. Falling back to initial ranking.")
            return candidates[:k]

"""Unit tests for EmbeddingService dimension validation and embedding generation."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from app.core.exceptions import VectorDimensionMismatchError
from app.embeddings.service import EmbeddingService


def test_embedding_dimension_validation_success():
    service = EmbeddingService(expected_dimension=384)
    valid_vector = [0.1] * 384
    # Should not raise
    service.validate_dimension(valid_vector)


def test_embedding_dimension_validation_failure():
    service = EmbeddingService(expected_dimension=384)
    invalid_vector = [0.1] * 128
    with pytest.raises(VectorDimensionMismatchError) as exc_info:
        service.validate_dimension(invalid_vector)
    assert "expected 384, received 128" in exc_info.value.message


def test_embed_text_with_mock_model():
    service = EmbeddingService(expected_dimension=384)
    mock_model = MagicMock()
    mock_model.encode.return_value = np.zeros(384)
    service._model = mock_model

    vec = service.embed_text("test sentence")
    assert len(vec) == 384
    mock_model.encode.assert_called_once()

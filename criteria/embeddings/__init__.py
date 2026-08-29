"""Embedding providers for semantic major search (docs/semantic-search.md)."""

from .base import (EmbeddingError, EmbeddingProvider, FakeProvider,
                   VectorIndex, cosine, rank_by_similarity)

__all__ = ['EmbeddingError', 'EmbeddingProvider', 'FakeProvider',
           'VectorIndex', 'cosine', 'rank_by_similarity']

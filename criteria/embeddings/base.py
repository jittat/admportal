"""
Embedding provider interface and vector maths.

Phase 1 of docs/semantic-search.md.  Two methods, because that is all the
feature needs: the majors are embedded once per admission cycle
(embed_documents) and a visitor's query is embedded on the fly (embed_query).

Providers are separated from the ranking so that the Phase 1 bake-off, the
Phase 3 generation script and the Phase 4 runtime all rank identically and only
the source of the vectors changes.

No Django import at module scope, so the doctests run standalone:

    python -m doctest criteria/embeddings/base.py -v
"""

import hashlib
import math
import random

import numpy as np


class EmbeddingError(Exception):
    """A provider could not return vectors.

    Phase 4 treats this as a degrade path, not an error path: the search page
    renders its exact results and drops the related section.
    """


class EmbeddingProvider:
    """Interface. `name` and `model` identify a vector set in storage.

    Subclasses implement embed_documents; embed_query defaults to it.  Some
    providers want an asymmetric query encoding, which is why it is a separate
    method rather than a caller convention.
    """

    name = 'base'
    model = ''
    dimensions = 0

    def embed_documents(self, texts):
        """Embed a list of texts, returning one vector per text, in order."""
        raise NotImplementedError

    def embed_query(self, text):
        """Embed a single query string."""
        return self.embed_documents([text])[0]

    def __str__(self):
        return '%s:%s' % (self.name, self.model)


class FakeProvider(EmbeddingProvider):
    """Deterministic vectors derived from the text, so tests never hit the network.

    The vectors are meaningless as semantics -- unrelated texts land at
    arbitrary similarities -- so use this to test plumbing (caching, batching,
    degrade paths, result assembly), not retrieval quality.  Where a test needs
    a *specific* ranking, pass `vectors` to pin the texts that matter; anything
    not pinned still gets its hash vector.

    >>> p = FakeProvider(dimensions=4)
    >>> p.embed_query('หมอ') == p.embed_query('หมอ')
    True
    >>> p.embed_query('หมอ') == p.embed_query('ครู')
    False
    >>> round(sum(x * x for x in p.embed_query('หมอ')), 6)
    1.0
    >>> pinned = FakeProvider(dimensions=2, vectors={'a': [1.0, 0.0]})
    >>> pinned.embed_query('a')
    [1.0, 0.0]
    """

    name = 'fake'
    model = 'fake'

    def __init__(self, dimensions=8, vectors=None):
        self.dimensions = dimensions
        self.vectors = dict(vectors or {})
        self.call_count = 0
        self.embedded = []

    def _hash_vector(self, text):
        seed = int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest()[:8],
                              'big')
        rng = random.Random(seed)
        vector = [rng.random() * 2 - 1 for _ in range(self.dimensions)]
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def embed_documents(self, texts):
        self.call_count += 1
        self.embedded.extend(texts)
        return [self.vectors.get(t) or self._hash_vector(t) for t in texts]


def cosine(a, b):
    """Cosine similarity of two equal-length vectors.

    Pure Python on purpose: this is the pairwise spot-check used in tests and
    one-off scripts, where building a numpy array costs more than it saves.
    Ranking a corpus goes through VectorIndex instead.

    Returns 0.0 for a zero vector rather than dividing by zero: a provider that
    returns one is broken, but a public search page is not the place to raise.

    >>> cosine([1.0, 0.0], [1.0, 0.0])
    1.0
    >>> cosine([1.0, 0.0], [0.0, 1.0])
    0.0
    >>> cosine([1.0, 0.0], [-1.0, 0.0])
    -1.0
    >>> cosine([1.0, 0.0], [0.0, 0.0])
    0.0
    >>> cosine([1.0], [1.0, 0.0])
    Traceback (most recent call last):
        ...
    ValueError: vectors differ in length: 1 vs 2
    """
    if len(a) != len(b):
        raise ValueError('vectors differ in length: %d vs %d' % (len(a), len(b)))

    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class VectorIndex:
    """A corpus of labelled vectors, ready to be searched.

    The rows are unit-normalized once, at construction, so a search is a single
    matrix-vector product rather than 290 separate cosines.  That is the whole
    point of the class: the majors change once per admission cycle and the
    queries arrive continuously, so all the per-vector work belongs on the
    build side.  Phase 4 holds one of these in a module-level cache per worker.

    Vectors are stored as float32 -- half the memory of float64, ample
    precision for a cosine, and the same width Phase 3 packs into its
    BinaryField.

    >>> index = VectorIndex(['a', 'b', 'c'],
    ...                     [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]])
    >>> len(index)
    3
    >>> [label for label, score in index.search([1.0, 0.0])]
    ['a', 'c', 'b']
    >>> index.search([1.0, 0.0], limit=1)
    [('a', 1.0)]
    >>> [label for label, score in index.search([1.0, 0.0], floor=0.5)]
    ['a', 'c']
    >>> VectorIndex([], []).search([1.0, 0.0])
    []
    """

    def __init__(self, labels, vectors):
        self.labels = list(labels)
        if len(self.labels) != len(vectors):
            raise ValueError('%d labels for %d vectors'
                             % (len(self.labels), len(vectors)))

        if not self.labels:
            self.matrix = np.zeros((0, 0), dtype=np.float32)
            return

        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        # a zero row would divide to nan and poison every later comparison
        norms[norms == 0] = 1.0
        self.matrix = matrix / norms

    def __len__(self):
        return len(self.labels)

    @property
    def dimensions(self):
        return int(self.matrix.shape[1]) if len(self.labels) else 0

    def search(self, query_vector, floor=None, limit=None):
        """Rank the corpus against a query vector, most similar first.

        Ties keep corpus order, so a ranking is reproducible across runs.
        `floor` drops anything below a similarity and `limit` caps the result;
        both are Phase 4 knobs tuned against the Phase 0 eval set -- a floor set
        too low is worse than not shipping.
        """
        if not self.labels:
            return []

        query = np.asarray(query_vector, dtype=np.float32)
        if query.shape != (self.dimensions,):
            raise ValueError('query has %s dimensions, corpus has %d'
                             % (query.shape, self.dimensions))

        norm = float(np.linalg.norm(query))
        scores = self.matrix @ (query / norm if norm else query)

        # stable, so equal scores come back in corpus order
        order = np.argsort(-scores, kind='stable')
        if limit is not None:
            order = order[:limit]

        ranked = [(self.labels[i], float(scores[i])) for i in order]
        if floor is not None:
            ranked = [pair for pair in ranked if pair[1] >= floor]
        return ranked


def rank_by_similarity(query_vector, corpus, floor=None, limit=None):
    """Rank (label, vector) pairs against a query vector, most similar first.

    A convenience wrapper that builds a VectorIndex and throws it away.  Fine
    for a one-off; for repeated queries against one corpus build the index once
    and call search(), or the normalization is paid per query.

    >>> corpus = [('a', [1.0, 0.0]), ('b', [0.0, 1.0]), ('c', [0.7, 0.7])]
    >>> [label for label, score in rank_by_similarity([1.0, 0.0], corpus)]
    ['a', 'c', 'b']
    >>> rank_by_similarity([1.0, 0.0], corpus, limit=1)
    [('a', 1.0)]
    >>> [label for label, score in rank_by_similarity([1.0, 0.0], corpus, floor=0.5)]
    ['a', 'c']
    """
    index = VectorIndex([label for label, _ in corpus],
                        [vector for _, vector in corpus])
    return index.search(query_vector, floor=floor, limit=limit)

"""
The Phase 1 bake-off: score candidate embedding models on the Phase 0 eval set.

docs/semantic-search.md.  Embeds the 159 distinct major titles and each eval
query through OpenRouter, ranks by cosine, and prints recall@5 / MRR per band
next to the substring baseline.

    python eval_embeddings.py --fake                 # plumbing only, no network
    python eval_embeddings.py --allow-unreviewed     # spend money
    python eval_embeddings.py --models qwen/qwen3-embedding-8b,baai/bge-m3

Two guards, both deliberate:

  * Nothing hits the network without --allow-unreviewed while any eval label is
    still unreviewed.  Choosing a model against an unreviewed gold set is the
    failure this whole phase ordering exists to prevent, and it fails silently:
    you get a table of plausible numbers that mean nothing.

  * Vectors are cached to data/embedding-cache/ (git-ignored) keyed by model and
    text hash, so re-running a model is free and adding a model only pays for
    that model.

Output: a table per model.  That table is the go/no-go for Phases 3-7.
"""

import argparse
import hashlib
import json
import os
import sys

from django_bootstrap import bootstrap

bootstrap()

from criteria.evaluation import (load_eval_set, evaluate, format_report,
                                 substring_ranking, DEFAULT_K)
from criteria.embeddings import EmbeddingError, FakeProvider, VectorIndex
from criteria.embeddings.corpus import source_texts
from criteria.embeddings.openrouter import OpenRouterProvider

# every candidate is multilingual; a local model was considered and dropped
# (docs/semantic-search.md, Decisions already taken)
CANDIDATE_MODELS = [
    'qwen/qwen3-embedding-8b',
    'baai/bge-m3',
    'voyage/voyage-4',
    'openai/text-embedding-3-large',
    'google/gemini-embedding-2',
]

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data', 'embedding-cache')


class VectorCache:
    """Text -> vector, on disk, per model.  Keyed by hash so it survives edits."""

    def __init__(self, model, directory=CACHE_DIR, enabled=True):
        self.enabled = enabled
        safe = model.replace('/', '__').replace(':', '__')
        self.path = os.path.join(directory, '%s.json' % safe)
        self.vectors = {}
        self.hits = 0
        self.misses = 0
        if enabled and os.path.exists(self.path):
            with open(self.path, encoding='utf-8') as f:
                self.vectors = json.load(f)

    @staticmethod
    def key(text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get_many(self, texts):
        """Split texts into cached vectors and the ones still to embed."""
        known, missing = {}, []
        for text in texts:
            vector = self.vectors.get(self.key(text)) if self.enabled else None
            if vector is None:
                missing.append(text)
            else:
                known[text] = vector
        self.hits += len(known)
        self.misses += len(missing)
        return known, missing

    def put_many(self, texts, vectors):
        for text, vector in zip(texts, vectors):
            self.vectors[self.key(text)] = vector

    def save(self):
        if not self.enabled:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.vectors, f)


def embed_with_cache(provider, texts, cache):
    """Embed texts, calling the provider only for what the cache lacks."""
    known, missing = cache.get_many(texts)
    if missing:
        cache.put_many(missing, provider.embed_documents(missing))
        known.update({t: cache.vectors[cache.key(t)] for t in missing})
    return [known[t] for t in texts]


def build_ranker(provider, cache, k):
    """A query -> ranked titles function backed by one embedding model.

    The index is built once and closed over, so the 39 eval queries pay for
    normalizing the corpus once between them rather than 39 times.
    """
    pairs = source_texts()
    vectors = embed_with_cache(provider, [text for _, text in pairs], cache)
    index = VectorIndex([title for title, _ in pairs], vectors)

    def rank(query):
        query_vector = embed_with_cache(provider, [query], cache)[0]
        # no floor here: the floor is a Phase 4 knob, and applying one now
        # would hide how far down the list a correct answer actually sits
        return [title for title, score in index.search(query_vector, limit=k)]

    return rank, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', default=','.join(CANDIDATE_MODELS),
                        help='comma-separated OpenRouter model ids')
    parser.add_argument('--fake', action='store_true',
                        help='use FakeProvider: exercises the plumbing with no '
                             'network and no key. The scores are meaningless.')
    parser.add_argument('--allow-unreviewed', action='store_true',
                        help='run against unreviewed eval labels anyway')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--k', type=int, default=DEFAULT_K)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    eval_set = load_eval_set()
    unreviewed = [e for e in eval_set['queries'] if not e.get('reviewed')]

    if unreviewed and not args.fake and not args.allow_unreviewed:
        print('%d of %d eval labels are not human-reviewed.'
              % (len(unreviewed), len(eval_set['queries'])))
        print()
        print('A bake-off against an unreviewed gold set produces a table of')
        print('plausible numbers that select a model on nothing. Review the')
        print('labels first (docs/semantic-search.md, Phase 0), or pass')
        print('--allow-unreviewed if you know why you want provisional numbers.')
        print('--fake needs no flag: it makes no API calls.')
        return 2

    if unreviewed:
        print('WARNING: %d unreviewed labels. These numbers are provisional.'
              % len(unreviewed))
        print()

    baseline = evaluate(substring_ranking, eval_set, args.k)
    print(format_report(baseline, 'baseline: substring search (no embeddings)'))
    print()

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    if args.fake:
        models = ['fake']

    summary = [('substring baseline',
                baseline['overall']['recall_at_k'],
                baseline['overall']['mrr'],
                baseline['overall']['false_positives'])]

    for model in models:
        if args.fake:
            provider = FakeProvider(dimensions=64)
        else:
            provider = OpenRouterProvider(model=model)
        cache = VectorCache(model, enabled=not args.no_cache)

        try:
            rank, index = build_ranker(provider, cache, args.k)
            report = evaluate(rank, eval_set, args.k)
        except EmbeddingError as e:
            print('%s FAILED: %s' % (model, e))
            print()
            continue
        finally:
            cache.save()

        print(format_report(report, 'model: %s  (%d titles, %d dims, '
                                    '%d cached / %d embedded, %d requests)'
                            % (model, len(index), index.dimensions,
                               cache.hits, cache.misses,
                               getattr(provider, 'request_count', 0))))
        print()

        if args.verbose:
            for r in report['results']:
                if 'recall_at_k' in r:
                    print('  %-24s recall %.2f  rr %.2f  %s'
                          % (r['query'], r['recall_at_k'],
                             r['reciprocal_rank'], ', '.join(r['returned'])))
                else:
                    print('  %-24s %d false positive(s): %s'
                          % (r['query'], r['false_positives'],
                             ', '.join(r['returned'])))
            print()

        summary.append((model, report['overall']['recall_at_k'],
                        report['overall']['mrr'],
                        report['overall']['false_positives']))

    print('%-34s %9s  %6s  %s' % ('', 'recall@%d' % args.k, 'MRR', 'FP/neg'))
    print('-' * 62)
    for name, recall, mrr, fp in summary:
        print('%-34s %9.3f  %6.3f  %6.2f' % (name, recall, mrr, fp))
    print()
    print('Go/no-go for Phases 3-7: does the best model beat the baseline by')
    print('enough on colloquial and career-phrased queries to be worth a')
    print('runtime API dependency? If not, the work stops here.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

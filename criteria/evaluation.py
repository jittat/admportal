"""
Scoring for the major-search eval set (criteria/evaldata/major_search_eval.json).

Phase 0 of docs/semantic-search.md.  The eval set decides which embedding
provider is chosen in Phase 1 and whether Claude enrichment earns its place in
Phase 2, so the metrics live here rather than inside a one-off script: both the
substring baseline (scripts/eval_baseline.py) and the later bake-off score
against the same code.

Ranking is over *titles*, not MajorCuptCode rows.  A title sits on several rows
whenever the same major runs at more than one campus, in more than one
programme type, or -- for 49 rows in the 2570 data -- with several major_title
tracks under one title (ศษ.บ. ศึกษาศาสตร์ alone has eight).  290 rows are 159
distinct titles.  Left as rows, one popular title could fill a top-5 by itself
and make recall@5 meaningless, so the eval labels titles and a ranker under
test must collapse its row ranking to titles, best rank winning -- dedupe()
does exactly that.

Like criteria/search.py this module does not import Django at module scope, so
its doctests run standalone:

    python -m doctest criteria/evaluation.py -v
"""

import json
import os

EVAL_SET_PATH = os.path.join(os.path.dirname(__file__),
                             'evaldata', 'major_search_eval.json')

DEFAULT_K = 5

# queries in this band have no correct answer; they measure precision instead
NEGATIVE_BAND = 'negative'


def load_eval_set(path=EVAL_SET_PATH):
    """Load the eval set fixture."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dedupe(titles):
    """Drop repeats, keeping first-seen order.

    >>> dedupe(['a', 'b', 'a', 'c'])
    ['a', 'b', 'c']
    """
    seen = set()
    result = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def recall_at_k(ranked, expected, k=DEFAULT_K):
    """Fraction of the expected titles reachable in the top k.

    Normalized by min(len(expected), k), not by len(expected): a query with
    eight correct answers cannot put more than five of them in a top-5, and
    scoring it out of eight would punish the breadth of the gold label rather
    than the ranking.

    >>> recall_at_k(['a', 'b', 'c'], ['a', 'b'], k=3)
    1.0
    >>> recall_at_k(['x', 'y', 'a'], ['a', 'b'], k=3)
    0.5
    >>> recall_at_k(['a'] + ['x'] * 9, ['a', 'b', 'c', 'd', 'e', 'f', 'g'], k=5)
    0.2
    >>> recall_at_k(['x'], [])
    0.0
    """
    if not expected:
        return 0.0
    expected_set = set(expected)
    hits = len([t for t in ranked[:k] if t in expected_set])
    return hits / min(len(expected_set), k)


def reciprocal_rank(ranked, expected):
    """1 / rank of the first correct title, or 0 if none is ranked.

    >>> reciprocal_rank(['a', 'b'], ['a'])
    1.0
    >>> reciprocal_rank(['x', 'a'], ['a'])
    0.5
    >>> reciprocal_rank(['x', 'y'], ['a'])
    0.0
    """
    expected_set = set(expected)
    for i, title in enumerate(ranked):
        if title in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def score_query(entry, ranked, k=DEFAULT_K):
    """Score one eval entry against a ranked title list.

    Negative-band entries have no correct answer, so they carry no recall or
    MRR; what is measured is how many majors were offered at all.

    >>> e = {'query': 'q', 'band': 'field_level', 'expected': ['a']}
    >>> score_query(e, ['a', 'b'])['recall_at_k']
    1.0
    >>> n = {'query': 'q', 'band': 'negative', 'expected': []}
    >>> score_query(n, ['a', 'b'])['false_positives']
    2
    """
    ranked = dedupe(ranked)
    result = {
        'query': entry['query'],
        'band': entry['band'],
        'expected': entry['expected'],
        'returned': ranked[:k],
    }
    if entry['band'] == NEGATIVE_BAND:
        result['false_positives'] = len(ranked[:k])
    else:
        result['recall_at_k'] = recall_at_k(ranked, entry['expected'], k)
        result['reciprocal_rank'] = reciprocal_rank(ranked, entry['expected'])
    return result


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def evaluate(rank_fn, eval_set=None, k=DEFAULT_K):
    """Run rank_fn over the whole eval set and summarize by band.

    rank_fn takes a query string and returns major titles, best first.

    >>> es = {'queries': [
    ...     {'query': 'a', 'band': 'near_exact', 'expected': ['A']},
    ...     {'query': 'b', 'band': 'negative', 'expected': []}]}
    >>> r = evaluate(lambda q: ['A'], es)
    >>> r['overall']['recall_at_k'], r['overall']['mrr']
    (1.0, 1.0)
    >>> r['bands']['negative']['false_positives']
    1.0
    """
    if eval_set is None:
        eval_set = load_eval_set()

    results = [score_query(e, list(rank_fn(e['query'])), k)
               for e in eval_set['queries']]

    bands = {}
    for band in dedupe([r['band'] for r in results]):
        in_band = [r for r in results if r['band'] == band]
        if band == NEGATIVE_BAND:
            bands[band] = {
                'n': len(in_band),
                'false_positives': _mean([r['false_positives']
                                          for r in in_band]),
            }
        else:
            bands[band] = {
                'n': len(in_band),
                'recall_at_k': _mean([r['recall_at_k'] for r in in_band]),
                'mrr': _mean([r['reciprocal_rank'] for r in in_band]),
            }

    scored = [r for r in results if r['band'] != NEGATIVE_BAND]
    negative = [r for r in results if r['band'] == NEGATIVE_BAND]

    return {
        'k': k,
        'results': results,
        'bands': bands,
        'overall': {
            'n': len(scored),
            'recall_at_k': _mean([r['recall_at_k'] for r in scored]),
            'mrr': _mean([r['reciprocal_rank'] for r in scored]),
            'n_negative': len(negative),
            'false_positives': _mean([r['false_positives']
                                      for r in negative]),
        },
    }


def format_report(report, title=''):
    """Render an evaluate() result as a fixed-width table."""
    k = report['k']
    lines = []
    if title:
        lines.append(title)
        lines.append('')
    lines.append('%-16s %4s  %9s  %6s' % ('band', 'n', 'recall@%d' % k, 'MRR'))
    lines.append('-' * 40)
    for band, stats in report['bands'].items():
        if band == NEGATIVE_BAND:
            lines.append('%-16s %4d  %9s  %6s   (%.2f false positives/query)'
                         % (band, stats['n'], '-', '-',
                            stats['false_positives']))
        else:
            lines.append('%-16s %4d  %9.3f  %6.3f'
                         % (band, stats['n'], stats['recall_at_k'],
                            stats['mrr']))
    lines.append('-' * 40)
    o = report['overall']
    lines.append('%-16s %4d  %9.3f  %6.3f'
                 % ('OVERALL', o['n'], o['recall_at_k'], o['mrr']))
    return '\n'.join(lines)


def substring_ranking(query):
    """Today's shipped search as a ranking function: matched titles, in view order.

    The baseline every embedding model is measured against, and -- once the
    related section ships -- the exact results that a semantic neighbour must
    not duplicate.  Needs the database; everything above this line does not.
    """
    # imported here, not at module scope, so that `python -m doctest` can load
    # this file as a top-level module without a package around it
    from .search import find_major_cupt_codes

    return [code.title for code in find_major_cupt_codes(query)]

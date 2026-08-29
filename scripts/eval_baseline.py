"""
Validate the major-search eval set against the live corpus, and score today's
substring search on it.

Phase 0 of docs/semantic-search.md.  Two jobs, deliberately in one script
because the second is meaningless without the first:

  1. Every expected title in criteria/evaldata/major_search_eval.json must
     exist in MajorCuptCode.  Titles change between admission cycles, so a
     label that was right for 2570 can quietly become unreachable -- and an
     unreachable label caps recall below 1.0 for reasons that have nothing to
     do with the retriever being measured.

  2. Score find_major_cupt_codes() -- the shipped substring search -- on the
     set.  This is the number semantic search has to beat.  Phase 1's bake-off
     table is only a go/no-go if there is a baseline in it.

Run from inside scripts/:

    python eval_baseline.py
    python eval_baseline.py --verbose     # per-query detail
"""

import sys

from django_bootstrap import bootstrap

bootstrap()

from criteria.evaluation import (load_eval_set, evaluate, format_report,
                                 substring_ranking, NEGATIVE_BAND)


def corpus_titles():
    from criteria.models import MajorCuptCode
    return set(MajorCuptCode.objects.values_list('title', flat=True))


def validate(eval_set, titles):
    """Report labels that no longer name a major.  Returns the problem count."""
    problems = 0
    seen_queries = set()

    for entry in eval_set['queries']:
        query = entry['query']
        if query in seen_queries:
            print('  DUPLICATE QUERY: %s' % query)
            problems += 1
        seen_queries.add(query)

        if entry['band'] not in eval_set['bands']:
            print('  UNKNOWN BAND %r on query %s' % (entry['band'], query))
            problems += 1

        if entry['band'] == NEGATIVE_BAND:
            if entry['expected']:
                print('  NEGATIVE QUERY WITH LABELS: %s' % query)
                problems += 1
            continue

        if not entry['expected']:
            print('  NO LABELS: %s' % query)
            problems += 1

        for title in entry['expected']:
            if title not in titles:
                print('  NOT IN CORPUS: %s -> %r' % (query, title))
                problems += 1

    return problems


def main():
    verbose = '--verbose' in sys.argv

    eval_set = load_eval_set()
    titles = corpus_titles()

    print('eval set: %d queries, labelled against corpus_year %s'
          % (len(eval_set['queries']), eval_set.get('corpus_year')))
    print('corpus:   %d distinct titles' % len(titles))
    print()

    print('validating labels...')
    problems = validate(eval_set, titles)
    if problems:
        print('  %d problem(s) -- fix these before trusting any score below.'
              % problems)
    else:
        print('  ok')
    print()

    unreviewed = [e['query'] for e in eval_set['queries']
                  if not e.get('reviewed')]
    if unreviewed:
        print('WARNING: %d of %d queries are not human-reviewed.'
              % (len(unreviewed), len(eval_set['queries'])))
        print('Scores below are provisional.  Do not choose an embedding')
        print('provider against an unreviewed gold set (docs/semantic-search.md,')
        print('Phase 0).')
        print()

    report = evaluate(substring_ranking, eval_set)
    print(format_report(report, 'baseline: find_major_cupt_codes (substring)'))
    print()

    if verbose:
        for r in report['results']:
            if r['band'] == NEGATIVE_BAND:
                mark = 'ok ' if r['false_positives'] == 0 else 'FP '
                print('%s %-24s returned %d' % (mark, r['query'],
                                                r['false_positives']))
            else:
                mark = 'ok ' if r['recall_at_k'] > 0 else 'MISS'
                print('%s %-24s recall %.2f  rr %.2f  %s'
                      % (mark, r['query'], r['recall_at_k'],
                         r['reciprocal_rank'],
                         ', '.join(r['returned']) or '(nothing)'))

    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())

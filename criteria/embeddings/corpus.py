"""
What gets embedded, and under what label.

Phase 1 of docs/semantic-search.md.  Kept apart from the providers because the
*text* is the variable Phase 2 changes: today a major is embedded as its bare
title, and enrichment will replace that with a few Thai sentences about what
the major covers.  Everything else -- the adapter, the cache, the ranking, the
eval -- stays put when that happens.

Labels are titles, not MajorCuptCode ids: ids are reassigned every admission
cycle, and 290 rows are 159 distinct titles (see criteria/evaluation.py).
"""


def distinct_titles():
    """Every distinct MajorCuptCode title, in a stable order."""
    # imported here so the module can be read without setting up Django
    from criteria.models import MajorCuptCode

    return sorted(set(MajorCuptCode.objects.values_list('title', flat=True)))


def source_texts(titles=None, enrichment=None):
    """Map each title to the text that represents it to an embedding model.

    Returns [(title, text)].  With no enrichment the text is the title itself,
    which is the Phase 1 baseline: whatever a model can do with 159 bare
    academic titles is the floor that Phase 2 has to beat before its cost and
    its model-written-prose risk are worth accepting.

    `enrichment` is a {title: text} mapping; titles it does not cover fall back
    to the bare title, so a partial enrichment run is still usable.

    >>> source_texts(['ก', 'ข'])
    [('ก', 'ก'), ('ข', 'ข')]
    >>> source_texts(['ก', 'ข'], {'ก': 'หมอ สัตว์'})
    [('ก', 'หมอ สัตว์'), ('ข', 'ข')]
    """
    if titles is None:
        titles = distinct_titles()
    enrichment = enrichment or {}

    return [(title, enrichment.get(title, title)) for title in titles]

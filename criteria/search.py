"""
Major search over the CUPT major taxonomy (MajorCuptCode).

The old search (majors.views.search_majors) matched majors.Major.simplified_title,
a normalized copy of the title stored on each row.  MajorCuptCode has no such
column, but there are only a few hundred codes, so matching is done in Python
over the whole table instead of adding a denormalized field.
"""

REMOVED_CHARS = "์ ()"


def simplify_title(title):
    """Normalize a major title for substring matching.

    Drops spaces, parentheses and the Thai character phinthu/thanthakhat so that
    titles match regardless of how the query is spaced or spelled out.

    >>> simplify_title('วิศวกรรมคอมพิวเตอร์')
    'วิศวกรรมคอมพิวเตอร'
    >>> simplify_title('วศ.บ. สาขาวิชาวิศวกรรมเคมี (ภาษาไทย ปกติ)')
    'วศ.บ.สาขาวิชาวิศวกรรมเคมีภาษาไทยปกติ'
    >>> simplify_title('  ')
    ''
    """
    return ''.join([c for c in title if c not in REMOVED_CHARS])


def matches(major_cupt_code, simplified_terms):
    """Check a code against already-simplified query terms (all must match).

    >>> class C: title, major_title = 'วิศวกรรมเคมี', ''
    >>> matches(C(), ['วิศวกรรม'])
    True
    >>> matches(C(), ['วิศวกรรม', 'ไฟฟ้า'])
    False
    """
    haystack = simplify_title(major_cupt_code.title)
    if major_cupt_code.major_title:
        haystack += simplify_title(major_cupt_code.major_title)

    return all([term in haystack for term in simplified_terms])


def find_major_cupt_codes(query):
    """Return the MajorCuptCodes whose title matches every term in query.

    An empty (or whitespace-only) query matches nothing.
    """
    simplified_terms = [simplify_title(t) for t in query.split()]
    simplified_terms = [t for t in simplified_terms if t != '']

    if not simplified_terms:
        return []

    # imported here so that the module (and its doctests) can be loaded
    # without setting up Django
    from .models import MajorCuptCode

    codes = MajorCuptCode.objects.select_related('faculty', 'campus').all()

    return [c for c in codes if matches(c, simplified_terms)]

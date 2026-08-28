# Major search

Public search for a major by name, at `/majors/search/` (`criteria:search-majors`). Given a Thai
major name it answers *"which admission projects accept this major, in which round, for how many
seats?"* — one result card per matched major, listing the projects underneath it.

Implemented in `criteria/search.py` (matching) and `criteria.views.search_majors` (assembly).

## 1. Request flow

```
GET /majors/search/?query=วิศวกรรมคอมพิวเตอร์
  │
  ├─ HIDE_CRITERIA        → 403          (criteria/views.py, same gate as the criteria pages)
  ├─ not ALLOW_SEARCH     → redirect /   (settings.py)
  ├─ blank query          → the form alone, no result section
  │
  ├─ find_major_cupt_codes(query)   criteria/search.py
  │     normalize query + every MajorCuptCode title, keep codes matching all terms
  │
  └─ build_search_results(codes)    criteria/views.py
        MajorCuptCode ──< CurriculumMajor >── AdmissionProject (major_detail_visible only)
                                  │
                                  └──< CurriculumMajorAdmissionCriteria (live criteria) → slots
```

### Matching (`criteria/search.py`)

`simplify_title` drops spaces, parentheses and the Thai `์`, mirroring `Major.simplify_title` from
the old implementation. Both the query and each candidate title are normalized, so a query matches
regardless of spacing or of whether the writer typed the thanthakhat.

The query is split on whitespace and **all** terms must appear — `วิศวกรรม เคมี` matches
`วศ.บ. สาขาวิชาวิศวกรรมเคมี`, `วิศวกรรม ไฟฟ้า` does not. `major_title` is searched alongside
`title` (it is empty for every row in the 2570 data, but populated in other cycles).

Matching runs **in Python over the whole table**, not in SQL. There are only a few hundred
`MajorCuptCode` rows (290 in 2570) and a full scan measures ~20ms, so no `simplified_title` column,
migration or index is needed. If the taxonomy ever grows by an order of magnitude, this is the
place to revisit.

`criteria/search.py` avoids importing models at module scope so its doctests run standalone:

```bash
python -m doctest criteria/search.py -v
```

### Result assembly (`criteria.views.build_search_results`)

- **Visibility.** Only `major_detail_visible=True` projects appear. That is the same flag
  `show_project` gates on, so every "อ่านเกณฑ์" link lands on a page anonymous visitors can read.
  (`is_available`, used by the criteria browser, is a *separate* hand-set flag — see § 4.)
- **The join is authoritative.** Projects come from `CurriculumMajor`, not from the denormalized
  `MajorCuptCode.admission_project_list`, whose rebuilder `update_project_list()` is commented out
  in `criteria/views.py` and may be stale.
- **Slots** are summed per (major, project) by `collect_slots` over
  `CurriculumMajorAdmissionCriteria`, skipping rows whose `AdmissionCriteria.is_deleted`. One query
  for the whole result set, not one per major. A sum of `0` across live criteria means a shared
  quota (see § 4), not an absent one.
- **Ordering.** Result cards follow the matched codes' order (faculty, then title); project rows
  within a card sort by `default_round_number`, `display_rank`, `id` — by round, *not* by slots,
  unlike the criteria table, where majors within one criteria row sort by slots descending.

Each result is `{'major_cupt_code': code, 'project_rows': [{'project', 'round_number', 'slots',
'criteria_count'}, ...]}`. Majors with no visible project are dropped.

## 2. Why the old search died

The previous search (`majors.views.search_majors`, `org-majors:search-majors`) matched
`majors.Major.simplified_title`. `Major` is the old project-authored "org" view of majors, and the
current import procedure no longer populates it — in the 2570 database the table has **0 rows**,
against 290 `MajorCuptCode` / 1915 `CurriculumMajor` / 1552 live `AdmissionCriteria`, and every
`CurriculumMajor.major` FK is null. Any query it issued returned nothing, which is why the feature
was hidden rather than fixed.

That view, its template and its URL are still in the tree, unreferenced, alongside the rest of the
dead `Major`-based pages (`org-majors:index`, `org-majors:list-majors`). Note that
`majors/templates/majors/search.html` reverses `{% url 'majors:search-majors' %}` against app
namespace `org-majors` — it would raise `NoReverseMatch` if anything rendered it.

## 3. Entry points

| Where | File |
| --- | --- |
| Navbar link, on every page extending `base.html` | `main/templates/base.html`, guarded by the `allow_search` tag in `main/templatetags/adm_extras.py` |
| Landing-page form, under `สาขาและโครงการรับสมัคร` | `main/templates/main/include/search_normal.html`, included at `main/templates/main/index.html:30` |
| The form repeated on the results page | `criteria/templates/criteria/include/search_form.html` |
| Floating desktop form (legacy) | `main/templates/main/include/search_float.html` — still only included from a `{% comment %}` block in `index.html`, so it does not render |

All forms are `method="get"`, so a result page can be linked and bookmarked.

Templates: `criteria/templates/criteria/search.html` plus
`criteria/templates/criteria/include/search_result_major.html` (one card).

## 4. Visibility and gating

| Flag | Used by |
| --- | --- |
| `is_available` | criteria browser (`criteria/views.py` `index`) — decides which projects become grid columns |
| `major_detail_visible` | **major search**; the `criteria:project-index` gate (403 for anonymous users); landing-page project list |

These are two separate per-project booleans, set by hand, with nothing keeping them in step; they
have drifted apart within a cycle before. Search deliberately follows `major_detail_visible` so its
links never lead to a 403.

Consequences worth knowing:

- Projects for rounds not yet released are silently absent from results. That is what
  `SEARCH_SCOPE_DISPLAY` ("จากโครงการรับสมัครในรอบที่ 1") and `SEARCH_EMPTY_DISPLAY_MESSAGE` exist
  to explain — **per-cycle copy in `settings.py` that must be reviewed as each round opens.**
- A visible project whose criteria are not imported yet yields `criteria_count == 0`; the card shows
  `-` instead of a slot count rather than a misleading `0`.
- **Zero slots mean a shared quota.** A criteria may record its whole quota against one major and
  `0` against its siblings — in the 2570 data every zero sits under a criteria with a non-zero
  sibling; there is no criteria whose majors are all zero. Such rows show
  `*จำนวนรับรวมกับเงื่อนไขอื่น`, the same wording the criteria table uses, rather than `0`, which
  would read as "no seats". The criteria pages had the matching bug — a `slots__gt=0` filter in
  `prepare_admission_criteria` dropped those majors outright — fixed alongside this.
- A (major, project) pair can legitimately carry several live criteria with separate quotas. Slots
  are summed and a `N เกณฑ์` badge points the reader at the project's criteria page for the
  breakdown.

## 5. Tests

`criteria/tests.py` covers `simplify_title`, `find_major_cupt_codes` (exact, normalized, all-terms,
blank, no-match) and the view (blank query, `ALLOW_SEARCH=False`, `HIDE_CRITERIA`, a visible hit,
exclusion of hidden-only projects, slot summing, deleted-criteria exclusion, round ordering).

```bash
./manage.py test criteria --settings=admportal.settings_test
```

The `--settings` override is needed because `settings_local.py` points at MySQL with an account that
cannot create a test database. See [Development › Testing](development.md#testing).

## 6. File map

```
criteria/search.py                              simplify_title, matches, find_major_cupt_codes
criteria/views.py                               search_majors, build_search_results, collect_slots
criteria/urls.py                                criteria:search-majors → /majors/search/
criteria/templates/criteria/search.html         results page
criteria/templates/criteria/include/            search_form.html, search_result_major.html
criteria/tests.py                               search tests
admportal/settings_test.py                      SQLite settings for the test runner

main/templates/base.html                        navbar search link
main/templatetags/adm_extras.py                 allow_search tag
main/templates/main/include/search_normal.html  landing-page form
admportal/settings.py                           ALLOW_SEARCH, SEARCH_SCOPE_DISPLAY,
                                                SEARCH_EMPTY_DISPLAY_MESSAGE
```

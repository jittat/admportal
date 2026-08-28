# Architecture

Three Django apps, wired together in `admportal/urls.py`.

| App | Role |
| --- | --- |
| `majors` | Core domain models (campus, faculty, project, round, major, CUPT taxonomy). Everything depends on these. |
| `criteria` | Admission-criteria/scoring models plus the main public criteria browser. |
| `main` | The landing page (`/`), announcements, and the admission calendar. |

The `criteria` app imports `majors` models but **not** vice-versa. Keep that dependency direction.

## URL mounting (note the mismatch)

```python
# admportal/urls.py
url(r'^$',            main.views.index,      name='main-index'),
url(r'^majors/',      include('criteria.urls')),   # app_name = 'criteria'
url(r'^org-majors/',  include('majors.urls')),     # app_name = 'org-majors'
url(r'^main/',        include('main.urls')),
url(r'^admin/',       admin.site.urls),
```

The paths and app modules are crossed: `criteria.urls` is served at `/majors/`, and `majors.urls`
is served at `/org-majors/`. Always use the namespaced URL names (`criteria:...`, `org-majors:...`,
`main-index`) rather than assuming the path.

## Request flows

### Landing page — `main.views.index` (`/`)

Renders `main/index.html` with:
- All admission rounds and campuses (for the calendar and navigation).
- Published `Announcement`s, grouped by round number. Announcements with no round attach to
  *every* round.
- Projects with `major_detail_visible=True`, ordered by `default_round_number`, `display_rank`.

### Criteria browser — `criteria.views.index` / `show_project` (`/majors/...`)

- `index` (optionally scoped by `campus_id` or `faculty_id`) lists the available admission projects
  (`is_available=True`) for the selection, using `MajorCuptCode.admission_project_list` to figure
  out which projects a campus/faculty participates in. `build_choices` builds the campus/faculty
  picker.
- `show_project` renders the full criteria report for one project. Non-`major_detail_visible`
  projects require an authenticated user. The heavy lifting is the criteria-row assembly described
  below.
- Both views short-circuit with `403` when the `HIDE_CRITERIA` flag is on.

### Major search — `criteria.views.search_majors` (`/majors/search/`)

A `GET` search (so results are linkable) over `MajorCuptCode` titles, reached from the landing-page
form and the navbar link. See [Major search](major-search.md) for the full description. In short:

- `criteria/search.py` normalizes the query and every candidate title with `simplify_title` and
  matches in Python over the whole table — a few hundred rows, so no denormalized column or index
  is needed. All whitespace-separated terms must match.
- `build_search_results` groups the hits **by major**: one entry per matched `MajorCuptCode`,
  listing the `major_detail_visible` projects that accept it, each with round number, summed slots
  and a live-criteria count.
- Honours `HIDE_CRITERIA` (403) and `settings.ALLOW_SEARCH` (redirect), and renders the bare form
  when no query is given.

### Public major listing & search — `majors.views` (`/org-majors/...`)

Obsolete, kept but unreferenced. These views read `majors.Major`, which the current import
procedure no longer populates (see [Major search § 2](major-search.md#2-why-the-old-search-died)).

- `list_majors` shows the majors under a project; `search_majors` was the previous search, a
  substring match over `Major.simplified_title`.
- `index` (the raw project list) requires login.

## Two rendering subtleties worth knowing

### 1. Precomputed table headers

Project major tables have nested, multi-row HTML `<th>` headers (rowspan/colspan). The source is an
org-mode-style outline stored in `AdmissionProject.column_descriptions`:

```
* หมวด A
** ย่อย A1
** ย่อย A2
* หมวด B
```

`majors/header_utils.py` parses this outline (`parse_header` → `traverse` → `table_header`) into the
HTML header, and also produces a list template (`table_header_as_list_template`) and a column count.
To avoid re-parsing on every request, `AdmissionProject.save()` recomputes and stores:

- `major_table_header_precomputed`
- `column_count`
- `major_description_list_template`

**Implication:** if you change header-parsing logic, existing rows must be re-saved for the change
to take effect. `header_utils.py` is also the one place with real (doc)tests.

### 2. Criteria row assembly (in views, not templates)

`criteria/views.py` builds the criteria table server-side before rendering:

1. `prepare_admission_criteria` — for each `AdmissionCriteria`, caches its score-criteria children
   (to avoid N+1 queries), attaches its curriculum majors, and produces one row per criteria plus a
   list of "free" majors with no criteria.
2. `combine_criteria_rows` — merges majors that appear under multiple criteria: when a major has
   slots in exactly one criteria (the rest zero), it collapses into a single combined row.

**Zero slots mean "shared quota", not "no seats".** A criteria may record its whole quota against
one major and `0` against its siblings; the table renders those as `*จำนวนรับรวมกับเงื่อนไขอื่น`.
Majors within a row are ordered by slots descending, so the quota-carrying major heads the row and
its zero-slot siblings follow (a stable sort — equal slots keep their existing order).
`prepare_admission_criteria` used to filter them out (`slots__gt=0`), which hid every major but the
quota-carrying one — on one 2570 project, 19 of 20 majors. The filter also made step 2 unreachable,
since with every row non-zero its "exactly one non-zero" condition can never hold.
3. `sort_admission_criteria_rows` — orders rows by faculty, then major code, then descending slots.

Raw score keys stored in JSON columns (`min_scores_json`, `scoring_scores_json`) are translated to
Thai display labels via `EXTRA_NAME_MAP` and `MIN_SCORE_COLUMNS` in the same module.

## Performance model

The criteria pages are query-heavy, so the codebase leans on **instance-level caching**
(`cached_*` attributes on `AdmissionCriteria` / `ScoreCriteria`) and **denormalized/precomputed
columns** (the precomputed header fields above, `curriculum_majors_json`,
`MajorCuptCode.admission_project_list`) rather than computing everything per request. When editing
data through means other than `save()`/the normal flows, these derived fields can go stale — refresh
them (re-save, or via the maintenance helpers `update_campus_keys` / `update_project_list` in
`criteria/views.py`).

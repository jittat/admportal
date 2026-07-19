# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Public-facing web portal ("admportal") that displays Kasetsart University's TCAS admission
information — admission projects, majors, admission rounds/calendar, and per-major admission
criteria (required scores, scoring weights). Content and UI are in Thai. It is a read-only
presentation layer: the authoritative data is authored in a separate `admapp` project and imported
here (see "Data import" below). Django 3.2 on Python 3.8.

Fuller documentation lives in [`docs/`](docs/README.md): [architecture](docs/architecture.md),
[data model](docs/data-model.md), [data import](docs/data-import.md), and
[development](docs/development.md).

## Commands

```bash
# Run the dev server (SQLite by default, unless settings_local.py overrides the DB)
./manage.py runserver

# Migrations
./manage.py makemigrations
./manage.py migrate

# Tests (Django test runner; note: the tests.py files are currently empty stubs)
./manage.py test              # all
./manage.py test criteria     # one app
./manage.py test criteria.tests.SomeTestCase.test_method   # single test

# Doctests live in majors/header_utils.py
python -m doctest majors/header_utils.py -v

# Load imported fixtures (see IMPORT-NOTES-65 for the full yearly procedure)
./manage.py loaddata data/<year>/<Model>.json
```

Dependencies are pinned in `requirements.txt` / `Pipfile` (Django 3.2, mysqlclient, pytz).

## Configuration

- `admportal/settings.py` holds defaults and app-specific config constants near the bottom:
  `ADMISSION_YEAR` (Buddhist-era, e.g. 2569), `ADMISSION_ROUND_COUNT`, `ALLOW_SEARCH`, and the
  Thai search-scope display strings. Update these each admission cycle.
- The DB defaults to SQLite. `admportal/settings_local.py` (git-ignored) overrides it — in practice
  a per-year MySQL database (`admportal<year>`). It is imported at the end of `settings.py`.
  It contains real credentials; never commit it or copy its contents elsewhere.
- `HIDE_CRITERIA` (module-level flag in `criteria/views.py`) hard-blocks the criteria pages with a
  403 when set — used to hide criteria before official release.

## Architecture

Three Django apps, wired in `admportal/urls.py`:

- **`majors`** — the core domain models. Everything else depends on these.
- **`criteria`** — admission criteria/scoring models plus the main public criteria browser.
- **`main`** — the site landing page (`/`), announcements, and the admission calendar.

Note the URL/app-name mismatch: `criteria.urls` is mounted at `/majors/` (app_name
`criteria`), and `majors.urls` is mounted at `/org-majors/` (app_name `org-majors`). Use the
namespaced names (`criteria:...`, `org-majors:...`) rather than assuming the path.

### Domain model (majors/models.py, criteria/models.py)

- `Campus` → `Faculty` → the two things a faculty offers.
- `AdmissionRound` — a TCAS round (has `number`, optional `subround_number`, `rank` for ordering,
  and calendar text). `AdmissionProject` links to rounds many-to-many through `AdmissionProjectRound`.
- `AdmissionProject` — an admission program. Two visibility flags matter:
  `is_available` (used by the criteria browser) and `major_detail_visible` (used by the public
  major listing/search; non-visible projects are gated behind login). `default_round_number` and
  `display_rank` drive ordering on the landing page.
- `Major` — a slot-bearing major under a project (the "org" / project-authored view).
- `MajorCuptCode` + `CurriculumMajor` — the CUPT-standardized major taxonomy, imported from
  `admapp`. `CurriculumMajor` is what admission criteria attach to.
- `AdmissionCriteria` — a versioned set of criteria for a project/faculty. It caches heavy child
  queries on the instance (`cache_score_criteria_children`, `get_all_*_score_criteria`) to avoid
  N+1s during rendering, and denormalizes majors into `curriculum_majors_json`.
- `ScoreCriteria` — a self-referential tree (`parent`/`childs`) of required vs. scoring criteria,
  combined with relations (AND/OR/SUM/MAX). Its `__str__`/`display_with_short_relation` render the
  human-readable Thai criteria text.
- The `criteria` app imports `majors` models but not vice-versa; keep that dependency direction.

### Two rendering subtleties worth knowing

- **Precomputed table headers.** Project major tables have nested, multi-row HTML `<th>` headers.
  `majors/header_utils.py` parses an org-mode-style outline (`* col`, `** subcol`) from
  `AdmissionProject.column_descriptions` into rowspan/colspan HTML. `AdmissionProject.save()`
  recomputes and stores `major_table_header_precomputed`, `column_count`, and
  `major_description_list_template` so templates don't re-parse on every request. If you change
  header logic, existing rows need re-saving.
- **Criteria row assembly** happens in `criteria/views.py`, not templates:
  `prepare_admission_criteria` → `combine_criteria_rows` (merges majors that share identical
  criteria and collapse to a single non-zero-slot row) → `sort_admission_criteria_rows`. The
  `EXTRA_NAME_MAP` / `MIN_SCORE_COLUMNS` tables translate raw score keys (from JSON columns) into
  Thai display labels.

### Data import (scripts/)

Standalone scripts, run from inside `scripts/` (they call `django_bootstrap.bootstrap()` to set up
Django, then use the ORM). They import CSVs / JSON exported from the `admapp` project. `IMPORT-NOTES-65`
documents the per-year procedure and ordering. Yearly source data lives under `data/<year>/`
(git-ignored). Note `.py~` (emacs backup) files litter the tree — the real files are the `.py` ones.

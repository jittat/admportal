# Data import

admportal does not author admission data — it **imports** it from the separate `admapp` project and
from CSV spreadsheets, then presents it. This happens once per admission cycle.

## How the scripts work

Import scripts live in `scripts/` and are plain Python scripts (not management commands). Each one
begins by bootstrapping Django so it can use the ORM:

```python
from django_bootstrap import bootstrap
bootstrap()   # adds cwd + parent to sys.path, sets DJANGO_SETTINGS_MODULE, calls django.setup()
```

Because `django_bootstrap.bootstrap()` appends the parent directory to `sys.path`, **run these from
inside the `scripts/` directory**:

```bash
cd scripts
python import_projects.py path/to/projects.csv
```

They read from the database configured in `settings_local.py`, so make sure it points at the
intended per-year database before running.

## Yearly source data

Per-year source files live under `data/<year>/` (git-ignored), e.g. `data/65/`, `data/67/r4/`.
JSON fixtures exported from `admapp` are loaded with `loaddata`; CSVs are consumed by the import
scripts.

## The scripts

| Script | Purpose |
| --- | --- |
| `import_campuses.py` | Import campuses. |
| `import_faculties.py` | Import faculties. |
| `import_projects.py` | Import admission projects from CSV (deletes + recreates by id). |
| `import_project_headers.py` | Import project header titles and default round numbers. |
| `import_majors.py` | Import majors under projects. |
| `import_missing_criterias.py` | Backfill criteria that failed to import. |
| `import_num_updates.py` | Import per-project update counts. |
| `extract_criteria_min_scores.py` | Populate `min_scores_json` on criteria. |
| `extract_criteria_scoring_scores.py` | Populate `scoring_scores_json` on criteria. |
| `simplify_major_titles.py` | Recompute `Major.simplified_title` for search. |
| `refresh_admission_projects.py` | Re-save projects (recomputes precomputed header fields). |
| `sync_campus_and_project_list.py` | Rebuild `MajorCuptCode.admission_project_list` / campus keys. |

`refresh_admission_projects.py` and `sync_campus_and_project_list.py` correspond to the derived-field
maintenance discussed in [Architecture › Performance model](architecture.md#performance-model) —
run them after bulk edits so the denormalized columns stay consistent.

## Reference procedure

`IMPORT-NOTES-65` at the repo root records the actual step-by-step ordering used for a past cycle
(create rounds → import campus/faculty → import projects → export `MajorCuptCode` /
`CurriculumMajor` from `admapp` and `loaddata` them here → import headers → import criteria). Use it
as the template for a new year, adjusting paths and the year directory.

Example `loaddata` step from that procedure:

```bash
./manage.py loaddata data/65/MajorCuptCode.json
./manage.py loaddata data/65/CurriculumMajor.json
```

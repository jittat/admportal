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

Per-year source files live under `data/<year>/` (git-ignored), e.g. `data/65/`, `data/67/r4/`,
`data/70/r1-json/`. JSON fixtures exported from `admapp` are loaded with `loaddata`; CSVs are
consumed by the import scripts.

## The fixture mismatch

Fixtures dumped from `admapp` cannot be fed to `loaddata` as-is. Two things differ:

1. **App label.** The core domain models live in an app called `appl` in `admapp`, but in `majors`
   here. So `Campus`, `Faculty`, `AdmissionProject`, `AdmissionRound` and `AdmissionProjectRound`
   arrive labelled `appl.*` and must be rewritten to `majors.*`. The `criteria` app is named the
   same in both projects, so the other five fixtures are already correctly labelled.

2. **Field sets.** `admapp` models carry application-flow and backoffice fields with no counterpart
   here — 29 extra on `AdmissionProject`, 12 on `AdmissionProjectRound`, 9 on `AdmissionCriteria`,
   6 on `AdmissionRound`, 2 on `Faculty`, and `add_limit` on `CurriculumMajorAdmissionCriteria`.
   These are dropped.

`scripts/fix_fixture_app_labels.py` does both. It derives the drop-list by diffing each fixture
against the live model via `apps.get_model`, rather than from a hardcoded list, so a field added in
`admapp` is handled automatically. Only the app-label renames are a maintained table
(`MODEL_RENAMES` at the top of the file); an unrecognised model label is a hard error.

> **Do not reach for `loaddata -i` instead.** `--ignorenonexistent` ignores unknown *fields*, but it
> also silently skips whole objects whose *model* is unknown. An unfixed `appl.campus` fixture
> loaded with `-i` installs zero rows and still reports success.

## The scripts

| Script | Purpose |
| --- | --- |
| `import_campuses.py` | Import campuses. |
| `import_faculties.py` | Import faculties. |
| `fix_fixture_app_labels.py` | Rewrite `admapp` fixtures to match this project's models. |
| `import_round_data.py` | **Main entry point.** Fix + load a round's 10 fixtures in one transaction. |
| `set_default_round_numbers.py` | Derive `AdmissionProject.default_round_number` from the round links. |
| `make_project_headers_csv.py` | Generate the "very short" header CSV, seeded from a previous year. |
| `import_projects.py` | Import admission projects from CSV. **Destructive — see below.** |
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

## Per-year procedure

Export all ten models from `admapp` into `data/<year>/<round>-json/`:

```bash
# in admapp
for M in Campus Faculty AdmissionRound AdmissionProject AdmissionProjectRound; do
    ./manage.py dumpdata appl.$M --indent=2 > ../admportal/data/70/r1-json/$M.json
done
for M in MajorCuptCode CurriculumMajor AdmissionCriteria ScoreCriteria \
         CurriculumMajorAdmissionCriteria; do
    ./manage.py dumpdata criteria.$M --indent=2 > ../admportal/data/70/r1-json/$M.json
done
```

Then, from `scripts/`:

```bash
python import_round_data.py ../data/70/r1-json
```

That fixes the fixtures into `data/70/r1-json-fixed/`, loads all ten in foreign-key order inside a
single transaction, and derives `default_round_number`. It prints the target database and row
counts and asks for confirmation first (`--yes` to skip). Because `loaddata` matches on primary key,
re-running it updates rows in place; it does not delete rows removed in `admapp` since the export.

Two things are not in the export and still need doing afterwards:

```bash
# 1. table_header_title -- hand-written abbreviated Thai column labels
python make_project_headers_csv.py ../data/70/projects-70-very-short.csv \
    --like ~/Dropbox/adm69/projects/projects-69-very-short.csv
#    edit the header_title column (a spreadsheet is easiest -- it contains newlines), then:
python import_project_headers.py ../data/70/projects-70-very-short.csv

# 2. derived score columns
python extract_criteria_min_scores.py
python extract_criteria_scoring_scores.py
```

Project ids are stable across years, so `--like` usually seeds every `header_title` and leaves only
new projects to write. It flags seeded values that mention a round, since the notation changes
between years (`รอบ 1/1` in 69 vs `รอบ 1.1` in 70).

A third field, `column_descriptions` (and therefore the precomputed table headers), is set per project by
`import_majors.py` from a separate CSV; it is empty in the fixture export. Until it is set,
`major_table_header_precomputed`, `column_count` and `major_description_list_template` stay empty —
`loaddata` bypasses `AdmissionProject.save()`, so any re-save (`refresh_admission_projects.py`) is
what recomputes them.

## `import_projects.py` is destructive

`import_projects.py` deletes and recreates each project by id. `AdmissionCriteria.admission_project`
and `CurriculumMajor.admission_project` are both `on_delete=CASCADE`, so **running it after the
criteria fixtures tears out the criteria tree underneath**, and it does so without a transaction.

Since `AdmissionProject.json` and `AdmissionProjectRound.json` are now part of the export, this
script is no longer needed in the normal procedure — the fixtures carry every field it set. Keep it
only for building projects when there is no `admapp` export to work from, and run it *before* any
criteria data exists.

## Older reference

`IMPORT-NOTES-65` at the repo root records the step-by-step ordering used for the 2565 cycle, from
before `AdmissionRound` / `AdmissionProjectRound` / `AdmissionProject` were exported. It predates
`import_round_data.py` and loads fixtures individually with `loaddata -i`; prefer the procedure
above.

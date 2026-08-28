# Development

## Requirements

- Python 3.10 (see `.python-version`)
- Django 5.2 (LTS), `mysqlclient`, `pytz` — pinned in `requirements.txt` / `Pipfile`

```bash
pip install -r requirements.txt
# or, with pipenv
pipenv install
```

## Commands

```bash
# Run the dev server (SQLite by default, unless settings_local.py overrides the DB)
./manage.py runserver

# Migrations
./manage.py makemigrations
./manage.py migrate

# Create an admin user (the /org-majors and non-visible pages require login)
./manage.py createsuperuser

# Import a round's data exported from admapp (see docs/data-import.md)
cd scripts && python import_round_data.py ../data/<year>/<round>-json
```

## Testing

```bash
./manage.py test --settings=admportal.settings_test                 # all apps
./manage.py test criteria --settings=admportal.settings_test        # one app
./manage.py test criteria.tests.SearchViewTest.test_no_match --settings=admportal.settings_test
```

`--settings=admportal.settings_test` is required in practice: `settings.py` ends by importing
`settings_local.py`, which points at the per-year MySQL database using an account that cannot
create `test_<dbname>`. `admportal/settings_test.py` swaps in an in-memory SQLite database.

> Note: `main/tests.py` and `majors/tests.py` are still empty stubs. The real tests are
> `criteria/tests.py` (major search) plus **doctests** in two modules:

```bash
python -m doctest majors/header_utils.py -v
python -m doctest criteria/search.py -v
```

## Configuration

App-specific config lives at the bottom of `admportal/settings.py` and should be updated each
admission cycle:

| Setting | Meaning |
| --- | --- |
| `ADMISSION_YEAR` | Buddhist-era year, e.g. `2569` |
| `ADMISSION_ROUND_COUNT` | Number of TCAS rounds |
| `ALLOW_SEARCH` | Enables the public major search |
| `SEARCH_SCOPE_DISPLAY`, `SEARCH_EMPTY_DISPLAY_MESSAGE` | Thai UI strings for search |

### Local settings & the database

The DB defaults to SQLite. `admportal/settings_local.py` (git-ignored) overrides it — in practice
a per-year MySQL database named `admportal<year>`. It is imported at the very end of `settings.py`:

```python
try:
    from admportal.settings_local import *
except ImportError:
    pass
```

`settings_local.py` contains **real database credentials**. Never commit it or copy its contents
elsewhere.

### Feature gate

`HIDE_CRITERIA` is a module-level flag in `criteria/views.py`. When set, the criteria pages —
including major search, whose results carry criteria-derived slot counts — return `403 Forbidden`.
Used to hide criteria from the public before official release.

`ALLOW_SEARCH` (in `settings.py`) hides the search forms and redirects `/majors/search/` back to the
landing page. `SEARCH_SCOPE_DISPLAY` and `SEARCH_EMPTY_DISPLAY_MESSAGE` are the per-cycle Thai copy
telling visitors which rounds the search currently covers — review them whenever a new round's
projects become `major_detail_visible`.

## Housekeeping notes

- The tree contains many `.py~` / `.html.org` / `.html.updated` files (emacs backups and
  work-in-progress copies). The real files are the plain `.py` / `.html` ones — ignore the rest.
- `data/` and `uploads/` are git-ignored; they hold per-year source data and uploaded media.

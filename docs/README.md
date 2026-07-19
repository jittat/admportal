# admportal Documentation

Public-facing web portal that displays Kasetsart University's TCAS admission information —
admission projects, majors, admission rounds/calendar, and per-major admission criteria
(required scores and scoring weights). Content and UI are in Thai.

It is a **read-only presentation layer**: the authoritative data is authored in a separate
`admapp` project and imported here. Django 3.2 on Python 3.8.

## Contents

- [Development](development.md) — setup, commands, configuration, testing.
- [Architecture](architecture.md) — apps, request flow, and the two non-obvious rendering
  mechanisms.
- [Data model](data-model.md) — the domain entities and how they relate.
- [Data import](data-import.md) — the per-year import workflow from `admapp`.

## Quick start

```bash
./manage.py migrate
./manage.py runserver
```

By default this uses a local SQLite database. Production and most real work use a per-year MySQL
database configured in `admportal/settings_local.py` (git-ignored). See
[Development › Configuration](development.md#configuration).

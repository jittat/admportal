# Data model

Models live in `majors/models.py`, `criteria/models.py`, and `main/models.py`.

## Entity relationships

```
Campus ──< Faculty ──< MajorCuptCode ──< CurriculumMajor >── AdmissionProject
                   │                         │        │
                   └──< Major >──────────────┘        │
                                                       │
AdmissionRound >──(AdmissionProjectRound)──< AdmissionProject
                                                       │
AdmissionProject ──< AdmissionCriteria ──< ScoreCriteria (self-referential tree)
                          │
                          └──(CurriculumMajorAdmissionCriteria)──< CurriculumMajor
```

## majors app

### `Campus` → `Faculty`
Top of the hierarchy. `Faculty` belongs to a `Campus` (`on_delete=PROTECT`).

### `AdmissionRound`
A TCAS round. Key fields: `number`, optional `subround_number` (0 = no subround), and `rank` for
ordering. `short_descriptions` and `admission_dates` hold calendar text shown on the landing page.

### `AdmissionProject`
An admission program. Linked to rounds many-to-many through `AdmissionProjectRound`.

Important flags and ordering fields:

| Field | Purpose |
| --- | --- |
| `is_available` | Used by the **criteria browser** to decide which projects to list. |
| `major_detail_visible` | Used by the **public major listing/search**; non-visible projects are gated behind login. |
| `default_round_number` | Which round the project is shown under. Portal-only; derived from the project's `AdmissionRound` at import time by `scripts/set_default_round_numbers.py`. |
| `display_rank` | Sort order within a round. |
| `column_descriptions` | Org-mode outline for the major table header (see [Architecture](architecture.md#1-precomputed-table-headers)). |
| `major_table_header_precomputed`, `column_count`, `major_description_list_template` | Derived, recomputed in `save()`. Do not edit by hand. |

### `Major`
A slot-bearing major under a project — the "org" / project-authored view of majors. Holds
`slots`, free-text `slots_comments`, and a CSV of detail items (`detail_items_csv`) rendered through
the project's list template. `simplified_title` is a normalized copy of the title used for search
(`Major.simplify_title` strips spaces, parentheses, and the Thai `์` character).

## criteria app

### `MajorCuptCode`
The CUPT-standardized major identity (`program_code` + `major_code`, unique together). Imported from
`admapp`. `admission_project_list` is a denormalized comma-separated list of project IDs this code
participates in — used by the criteria browser to avoid a join.

### `CurriculumMajor`
Ties a `MajorCuptCode` to an `AdmissionProject` (+ faculty/campus, and optionally a `Major`). This is
the entity that **admission criteria attach to**, via the `CurriculumMajorAdmissionCriteria` join
table (which carries `slots`).

`COMPONENT_WEIGHT_TYPE_CHOICES` (a large constant in `criteria/models.py`) enumerates the TCAS
"component weight" groups (CW…) used for scoring formulas.

### `AdmissionCriteria`
A **versioned** (`version`, `is_deleted`) set of admission criteria for a project/faculty. It:

- Caches heavy child queries on the instance — `get_all_required_score_criteria`,
  `get_all_scoring_score_criteria`, `cache_score_criteria_children` — to prevent N+1 queries during
  rendering.
- Denormalizes its majors into `curriculum_majors_json` via `save_curriculum_majors()`.
- Stores raw score data as JSON in `min_scores_json` and `scoring_scores_json`.

### `ScoreCriteria`
A **self-referential tree** (`parent` / `childs`) of individual criteria. Each node has:

- `criteria_type` — `required` (pass/fail thresholds) or `scoring` (weighted contributions).
- `relation` — how children combine: `AND` / `OR` / `SUM` / `MAX` (rendered to Thai via
  `get_relation_display`).
- `value`, `unit`, `description`, plus `primary_order` / `secondary_order` for layout.

`__str__` / `display_with_short_relation` produce the human-readable Thai criteria text shown in the
report.

## main app

### `Announcement`
Landing-page announcements. `is_published` gates visibility; `rank` then `-created_date` set the
order (`Meta.ordering`). An announcement may attach to an `AdmissionRound`; if it has none, the
landing page shows it under **every** round. `DEFAULT_ROUND_NUMBER = 2` is the fallback round.

"""
Set AdmissionProject.default_round_number from the project's admission round.

`default_round_number` is a portal-only field -- admapp has no counterpart, so
it is not in the export -- but it can be derived: it is the `number` of the
round the project is linked to through AdmissionProjectRound.  admapp does the
same thing in AdmissionProject.get_single_round_number().

AdmissionRound is ordered by `rank`, so for a project linked to more than one
round the lowest-ranked (earliest) one wins.  Those projects are reported so
they can be checked by hand.

Every project is re-saved, which also re-runs the precomputation that
AdmissionProject.save() does for major_table_header_precomputed,
column_count and major_description_list_template -- loaddata bypasses
save() entirely.  Note those three stay empty while column_descriptions is
empty (it is, for every project in the year-70 export): the header text is
set per project by import_majors.py, and re-saving after that is what
actually fills them in.

Run it after AdmissionProjectRound.json has been loaded.  import_round_data.py
calls it automatically; run it standalone to recompute:

    python set_default_round_numbers.py
"""

import django_bootstrap


def set_default_round_numbers(verbose=True):
    """Returns (changed, unchanged, projects_without_a_round)."""
    from majors.models import AdmissionProject

    changed = 0
    unchanged = 0
    no_round = []
    multi_round = []

    for project in AdmissionProject.objects.all():
        rounds = list(project.admission_rounds.all())
        if not rounds:
            no_round.append(project)
            continue
        if len(rounds) > 1:
            multi_round.append((project, rounds))

        number = rounds[0].number
        if project.default_round_number == number:
            unchanged += 1
        else:
            changed += 1
        project.default_round_number = number
        # Re-saved even when unchanged: save() re-runs the header
        # precomputation, which loaddata skips.
        project.save()

    if verbose:
        for project, rounds in multi_round:
            print('  NOTE: %s is in %d rounds (%s); used %s' %
                  (project.short_title, len(rounds),
                   ', '.join(str(r) for r in rounds), rounds[0]))
        for project in no_round:
            print('  WARNING: %s (id=%d) has no admission round; '
                  'default_round_number left at %d' %
                  (project.short_title, project.id,
                   project.default_round_number))
        print('  set default_round_number on %d project(s) '
              '(%d already correct, %d without a round)' %
              (changed, unchanged, len(no_round)))

    return changed, unchanged, no_round


def main():
    django_bootstrap.bootstrap()
    set_default_round_numbers()


if __name__ == '__main__':
    main()

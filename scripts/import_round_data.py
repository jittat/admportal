"""
Import a round's data, exported from admapp, into admportal.

This is the production entry point.  It does two things:

1. Rewrites the exported fixtures so they match this project's models
   (see fix_fixture_app_labels.py -- app label `appl` -> `majors`, plus
   dropping admapp-only fields).  Skip with --skip-fix if you already ran
   the fixer by hand.

2. Loads the fixed fixtures with loaddata, in foreign-key order, inside a
   single transaction.  If any file fails, nothing is committed.

`loaddata` matches on primary key, so re-running this over an already
imported round updates rows in place rather than duplicating them.  Rows
that were deleted in admapp since the last export are NOT removed here.

Usage (run from inside scripts/, like the other scripts here):

    python import_round_data.py ../data/70/r1-json
    python import_round_data.py ../data/70/r1-json --yes        # no prompt
    python import_round_data.py ../data/70/r1-json --skip-fix

Afterwards, these still need to be done by hand -- they are not in the
export (see IMPORT-NOTES-65):

  * python make_project_headers_csv.py <out.csv> --like <last-year.csv>
    then edit header_title, then:
    python import_project_headers.py <the-edited-file.csv>
    (only table_header_title is still hand-written; default_round_number
     is derived from the admission rounds during the load)
  * python extract_criteria_min_scores.py
  * python extract_criteria_scoring_scores.py
"""

import argparse
import os
import sys

import django_bootstrap
import fix_fixture_app_labels
import set_default_round_numbers

# Foreign keys must resolve as we go, so order matters.
LOAD_ORDER = [
    'Campus.json',
    'Faculty.json',
    'AdmissionRound.json',
    'AdmissionProject.json',
    'AdmissionProjectRound.json',
    'MajorCuptCode.json',
    'CurriculumMajor.json',
    'AdmissionCriteria.json',
    'ScoreCriteria.json',
    'CurriculumMajorAdmissionCriteria.json',
]

# Reported before and after the load, in LOAD_ORDER order.
COUNTED_MODELS = [
    ('majors', 'Campus'),
    ('majors', 'Faculty'),
    ('majors', 'AdmissionRound'),
    ('majors', 'AdmissionProject'),
    ('majors', 'AdmissionProjectRound'),
    ('criteria', 'MajorCuptCode'),
    ('criteria', 'CurriculumMajor'),
    ('criteria', 'AdmissionCriteria'),
    ('criteria', 'ScoreCriteria'),
    ('criteria', 'CurriculumMajorAdmissionCriteria'),
]


def check_files(fixed_dir):
    """Every file in LOAD_ORDER must exist, and nothing may be left over."""
    present = set(n for n in os.listdir(fixed_dir) if n.endswith('.json'))

    missing = [n for n in LOAD_ORDER if n not in present]
    if missing:
        raise SystemExit('ERROR: missing fixture(s) in %s: %s' %
                         (fixed_dir, ', '.join(missing)))

    extra = sorted(present - set(LOAD_ORDER))
    if extra:
        raise SystemExit(
            'ERROR: %s contains fixture(s) this script does not know where to '
            'load: %s.  Add them to LOAD_ORDER (in foreign-key order).' %
            (fixed_dir, ', '.join(extra)))


def counts():
    from django.apps import apps

    result = []
    for app_label, model_name in COUNTED_MODELS:
        model = apps.get_model(app_label, model_name)
        result.append((model_name, model.objects.count()))
    return result


def print_counts(label, rows):
    print(label)
    for name, n in rows:
        print('  %-32s %7d' % (name, n))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('indir', help='directory of exported .json fixtures')
    parser.add_argument('--fixed-dir',
                        help='where the fixed fixtures go / already are '
                             '(default: <indir>-fixed)')
    parser.add_argument('--skip-fix', action='store_true',
                        help='fixtures in --fixed-dir are already fixed')
    parser.add_argument('--yes', action='store_true',
                        help='do not ask for confirmation')
    args = parser.parse_args()

    indir = args.indir.rstrip('/')
    fixed_dir = (args.fixed_dir or (indir + '-fixed')).rstrip('/')

    django_bootstrap.bootstrap()

    from django.conf import settings
    from django.core.management import call_command
    from django.db import transaction

    if args.skip_fix:
        print('skipping fix step, loading from %s\n' % fixed_dir)
    else:
        print('fixing %s -> %s\n' % (indir, fixed_dir))
        fix_fixture_app_labels.fix_directory(indir, fixed_dir)
        print('')

    check_files(fixed_dir)

    db = settings.DATABASES['default']
    print('target database: %s (%s)' %
          (db.get('NAME'), db.get('ENGINE', '').rsplit('.', 1)[-1]))
    before = counts()
    print_counts('current row counts:', before)

    if not args.yes:
        answer = input('\nload %d fixtures into this database? [y/N] '
                       % len(LOAD_ORDER))
        if answer.strip().lower() not in ('y', 'yes'):
            raise SystemExit('aborted.')

    print('')
    with transaction.atomic():
        for name in LOAD_ORDER:
            path = os.path.join(fixed_dir, name)
            print('loading %s' % name)
            call_command('loaddata', path, verbosity=1)

        # Derived, not exported: needs the round links to be in place.
        # Re-saving each project also re-runs the header precomputation
        # that loaddata skips.
        print('\nsetting default_round_number from admission rounds')
        set_default_round_numbers.set_default_round_numbers()

    print('')
    print_counts('row counts after load:', counts())

    print('\nStill to do by hand (not in the export):')
    print('  * python make_project_headers_csv.py <out.csv> '
          '--like <last-year.csv>')
    print('      edit header_title, then import_project_headers.py <it>')
    print('      (only table_header_title is still hand-written)')
    print('  * python extract_criteria_min_scores.py')
    print('  * python extract_criteria_scoring_scores.py')


if __name__ == '__main__':
    main()

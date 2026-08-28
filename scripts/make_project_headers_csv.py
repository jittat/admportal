"""
Generate the "very short" project header CSV that import_project_headers.py
reads, pre-filled from the database.

`table_header_title` is a portal-only field with no counterpart in admapp: it
is a hand-written, heavily abbreviated Thai label for the criteria table
column header, so it cannot be derived and has to be authored by hand each
year.  This script produces the CSV skeleton so only the header_title column
is left to edit.

`default_round_number` is written out too, because import_project_headers.py
requires the column -- but it is already set in the database by
set_default_round_numbers.py, so the values here just round-trip.

With --like, header_title is seeded from a previous year's file, matched on
project id.  Project ids are stable across years, so this usually fills in
almost everything and leaves only new projects to write.  Seeded titles that
mention a round are flagged: the round notation changes between years
(e.g. "รอบ 1/1" in 69 vs "รอบ 1.1" in 70).

Run it after import_round_data.py.  Usage:

    python make_project_headers_csv.py ../data/70/projects-70-very-short.csv \
        --like ~/Dropbox/adm69/projects/projects-69-very-short.csv

Then edit header_title (a spreadsheet is easiest -- the field contains
newlines) and load it with:

    python import_project_headers.py <the-edited-file.csv>
"""

import argparse
import csv

import django_bootstrap

FIELDNAMES = ['id', 'title', 'header_title', 'default_round_number']


def read_seed(path):
    with open(path, newline='', encoding='utf-8') as f:
        return dict((r['id'], r['header_title'])
                    for r in csv.DictReader(f)
                    if r.get('id'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('outfile', help='CSV file to write')
    parser.add_argument('--like', metavar='CSV',
                        help="a previous year's very-short CSV to seed "
                             'header_title from, matched on project id')
    args = parser.parse_args()

    django_bootstrap.bootstrap()

    from majors.models import AdmissionProject

    seed = read_seed(args.like) if args.like else {}

    projects = AdmissionProject.objects.order_by('default_round_number',
                                                 'display_rank', 'id')
    seeded = 0
    blank = []
    check = []

    with open(args.outfile, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for p in projects:
            header_title = seed.get(str(p.id), '')
            if header_title:
                seeded += 1
                if 'รอบ' in header_title:
                    check.append((p, header_title))
            else:
                blank.append(p)
            writer.writerow({'id': p.id,
                             'title': p.title,
                             'header_title': header_title,
                             'default_round_number': p.default_round_number})

    print('wrote %s' % args.outfile)
    print('  %d project(s), %d header_title seeded, %d blank' %
          (projects.count(), seeded, len(blank)))
    for p in blank:
        print('    TO WRITE: id=%d %s' % (p.id, p.title))
    for p, header_title in check:
        print('    CHECK ROUND: id=%d %s -> %r' %
              (p.id, p.title, header_title))


if __name__ == '__main__':
    main()

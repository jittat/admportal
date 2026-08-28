"""
Rewrite fixtures exported from the `admapp` project so that they can be loaded
into admportal with `manage.py loaddata`.

Two things differ between the two projects:

1. The app label.  In admapp the core domain models live in an app called
   `appl`; here they live in `majors`.  See MODEL_RENAMES below.

2. The field sets.  admapp models carry extra fields (application-flow and
   backoffice concerns) that have no counterpart here.  Those fields are
   dropped.

Do NOT use `loaddata -i` instead of this script: `--ignorenonexistent` also
ignores whole objects whose *model* is unknown, so an unfixed `appl.campus`
fixture loads zero rows and still reports success.

Usage (run from inside scripts/, like the other scripts here):

    python fix_fixture_app_labels.py ../data/70/r1-json
    python fix_fixture_app_labels.py ../data/70/r1-json --out ../data/70/r1
"""

import argparse
import json
import os
import sys

import django_bootstrap

# Fixture model label -> admportal model label.
MODEL_RENAMES = {
    'appl.campus': 'majors.campus',
    'appl.faculty': 'majors.faculty',
    'appl.admissionproject': 'majors.admissionproject',
    'appl.admissionround': 'majors.admissionround',
    'appl.admissionprojectround': 'majors.admissionprojectround',
}

# Fields dropped even though a field of that name exists here, keyed by the
# label *after* renaming.  Nothing is listed at the moment; extra fields are
# normally detected automatically by diffing against the model.
FORCE_DROP_FIELDS = {}


def model_field_names(label):
    from django.apps import apps

    app_label, model_name = label.split('.')
    model = apps.get_model(app_label, model_name)
    names = set()
    for f in model._meta.concrete_fields:
        if not f.primary_key:
            names.add(f.name)
    for f in model._meta.many_to_many:
        names.add(f.name)
    return names


def fix_file(in_path, out_path, report):
    with open(in_path, encoding='utf-8') as f:
        objects = json.load(f)

    for obj in objects:
        old_label = obj['model']
        label = MODEL_RENAMES.get(old_label, old_label)
        if label != old_label:
            obj['model'] = label
            report.setdefault(label, {})['renamed_from'] = old_label

        try:
            keep = model_field_names(label)
        except LookupError:
            raise SystemExit(
                'ERROR: %s: no model matches %r.  Add an entry to '
                'MODEL_RENAMES.' % (in_path, label))
        keep -= FORCE_DROP_FIELDS.get(label, set())

        stats = report.setdefault(label, {})
        stats['count'] = stats.get('count', 0) + 1
        dropped = stats.setdefault('dropped', {})
        for name in list(obj['fields']):
            if name not in keep:
                del obj['fields'][name]
                dropped[name] = dropped.get(name, 0) + 1

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(objects, f, ensure_ascii=False, indent=2)


def fix_directory(indir, outdir, verbose=True):
    """Fix every .json fixture in indir, writing the result to outdir.

    Django must already be set up.  Returns {filename: report}.
    """
    os.makedirs(outdir, exist_ok=True)

    names = sorted(n for n in os.listdir(indir) if n.endswith('.json'))
    if not names:
        raise SystemExit('ERROR: no .json files in %s' % indir)

    reports = {}
    for name in names:
        report = {}
        fix_file(os.path.join(indir, name), os.path.join(outdir, name), report)
        reports[name] = report
        if verbose:
            print(name)
            for label in sorted(report):
                stats = report[label]
                renamed = stats.get('renamed_from')
                print('  %s%s: %d objects' %
                      (label,
                       ' (was %s)' % renamed if renamed else '',
                       stats['count']))
                for field, n in sorted(stats['dropped'].items()):
                    print('    dropped field %s (%d)' % (field, n))
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('indir', help='directory of exported .json fixtures')
    parser.add_argument('--out',
                        help='output directory (default: <indir>-fixed)')
    args = parser.parse_args()

    indir = args.indir.rstrip('/')
    outdir = args.out or (indir + '-fixed')

    django_bootstrap.bootstrap()
    reports = fix_directory(indir, outdir)

    print('\nwrote %d files to %s' % (len(reports), outdir))


if __name__ == '__main__':
    main()

from django_bootstrap import bootstrap
bootstrap()

import sys
import csv

from majors.models import Campus, AdmissionRound, AdmissionProject, AdmissionProjectRound

def main():
    filename = sys.argv[1]
    counter = 0
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')
        for r in reader:
            if 'id' not in r:
                continue

            project = AdmissionProject.objects.get(pk=r['id'])
            project.table_header_title = r['header_title']
            project.default_round_number = int(r['default_round_number'])
            project.save()

            counter += 1

    print('Imported',counter,'projects')
        

if __name__ == '__main__':
    main()
    

from django_bootstrap import bootstrap
bootstrap()

import sys
import csv

from majors.models import Campus, AdmissionRound, AdmissionProject

def main():
    admission_rounds = dict([(r.id,r) for r in AdmissionRound.objects.all()])
    
    filename = sys.argv[1]
    counter = 0
    with open(filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for items in reader:
            if len(items) < 7:
                continue

            pid = int(items[0])
            title = items[1]
            short_title = items[2]
            short_descriptions = items[3]
            slots = int(items[6])

            project = AdmissionProject(id=pid,
                                       title=title,
                                       short_title=short_title,
                                       short_descriptions=short_descriptions,
                                       slots=slots)
            
            if items[4] != '':
                campus = Campus.objects.get(pk=items[4])
                project.campus = campus

            project.save()

            prounds = [int(rid) for rid in items[5].split(';')]
            for r in prounds:
                project.admission_rounds.add(AdmissionRound.objects.get(pk=r))
            
            counter += 1

    print('Imported',counter,'faculties')
        

if __name__ == '__main__':
    main()
    

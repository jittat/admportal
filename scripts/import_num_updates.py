from django_bootstrap import bootstrap
bootstrap()

import sys
import csv

from criteria.models import *

ORG_SLOTS = 2
CURRENT_SLOTS = 3

AD_PRJ_COL = 5
PROGRAM_MAJOR_CODE = 6

def read_adjustment_csv(filename):
    rows = []
    with open(filename) as csvfile:
        reader = csv.reader(csvfile)
        for r in reader:
            rows.append(r)

    return rows

def extract_program_major_code(r):
    c = r[PROGRAM_MAJOR_CODE].strip()
    if len(c) == 15:
        return c,''
    else:
        return c[:15],c[16]

def main():
    adjustment_csv = sys.argv[1]

    rows = read_adjustment_csv(adjustment_csv)

    for r in rows:
        admission_project_id = int(r[AD_PRJ_COL])
        project = AdmissionProject.objects.get(pk=admission_project_id)
        
        original_slots = int(r[ORG_SLOTS])
        current_slots = int(r[CURRENT_SLOTS])

        program_code, major_code = extract_program_major_code(r)
        #print(admission_project_id, program_code, major_code)

        cupt_codes = MajorCuptCode.objects.filter(program_code=program_code,
                                                  major_code=major_code).all()


        if len(cupt_codes)!=1:
            print(f'ERROR not found,{program_code},{major_code},{r[0]},{r[1]}')
            continue

        cupt_code = cupt_codes[0]
        
        curriculum_majors = CurriculumMajor.objects.filter(cupt_code=cupt_code,
                                                          admission_project=project)

        cm_criteria = None
        error_not_unique = False
        if len(curriculum_majors)!=1:
            #print('CMAJOR ERROR (fixable)')

            for cm in curriculum_majors:
                for cr in CurriculumMajorAdmissionCriteria.objects.filter(curriculum_major=cm, admission_criteria__is_deleted=False):
                    #print(">>>", cr.slots, cr.admission_criteria.is_deleted)
                    if cm_criteria != None:
                        #print('***CMAJOR ERROR', program_code, major_code, admission_project_id, cupt_code, curriculum_majors)
                        error_not_unique = True
                    cm_criteria = cr
        else:
            curriculum_major = curriculum_majors[0]
            for cr in CurriculumMajorAdmissionCriteria.objects.filter(curriculum_major=curriculum_major, admission_criteria__is_deleted=False):
                #print(">>>", cr.slots, cr.admission_criteria.is_deleted)
                if cm_criteria != None:
                    #print('***CMAJOR ERROR', program_code, major_code, admission_project_id, cupt_code, curriculum_majors)
                    if cm_criteria.slots == 0:
                        cm_criteria = cr
                    elif cr.slots != 0:
                        error_not_unique = True
                else:
                    cm_criteria = cr

        if r[10] != '':
            cm_criteria = CurriculumMajorAdmissionCriteria.objects.get(pk=r[10])
            if error_not_unique:
                print('FIXED', cm_criteria)
                error_not_unique = False
                    
        if error_not_unique:
            candidates = []
            for cr in CurriculumMajorAdmissionCriteria.objects.filter(curriculum_major=curriculum_major, admission_criteria__is_deleted=False):
                if cr.slots == original_slots:
                    candidates.append(cr)

            if len(candidates) != 1:
                print('ERROR NOT UNIQUE', original_slots, program_code, major_code, admission_project_id, cupt_code, len(candidates), [c.id for c in candidates], original_slots, current_slots)
                #print('UNFIXABLE', candidates)
                continue
            else:
                cm_criteria = candidates[0]

        if cm_criteria.imported_slots == 0:
            cm_criteria.imported_slots = cm_criteria.slots

        if cm_criteria.imported_slots != original_slots:
            print('>>> ERROR SLOT MISMATCH', cm_criteria.slots, original_slots, program_code, major_code, admission_project_id, cupt_code)
            continue

        cm_criteria.slots = current_slots
        cm_criteria.save()
        

if __name__ == '__main__':
    main()


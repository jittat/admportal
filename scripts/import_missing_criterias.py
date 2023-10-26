from django_bootstrap import bootstrap
bootstrap()

import sys
import json

from criteria.models import *
from majors.models import Faculty

def main():
    filename = sys.argv[1]

    with open(filename) as f:
        data = json.loads(f.read())

    for k in data:
        print(k)

        program_code, major_code = k.split('-')

        old_major_cupt_codes = MajorCuptCode.objects.filter(program_code=program_code, major_code=major_code).all()

        if len(old_major_cupt_codes) != 0:
            major_cupt_code = old_major_cupt_codes[0]
        else:
            major_cupt_code = MajorCuptCode()

            major_cupt_code_data = data[k]['major_cupt_code']

            for f in major_cupt_code_data:
                if f != 'faculty':
                    setattr(major_cupt_code, f, major_cupt_code_data[f])
                else:
                    major_cupt_code.faculty = Faculty.objects.get(pk=major_cupt_code_data[f])

            major_cupt_code.campus = major_cupt_code.faculty.campus
            major_cupt_code.save()

        print('+major_cupt_code', major_cupt_code.id, major_cupt_code)

        criteria_data = data[k]['criterias']

        for project_id in criteria_data:
            print(f'---{project_id}---')

            admission_project = AdmissionProject.objects.get(pk=project_id)
            
            curriculum_major = CurriculumMajor()
            curriculum_major.admission_project = admission_project
            curriculum_major.cupt_code = major_cupt_code
            curriculum_major.faculty = major_cupt_code.faculty
            curriculum_major.campus = major_cupt_code.campus

            curriculum_major.save()
            print('+curriculum_major', curriculum_major.id)
            
            for one_criteria in criteria_data[project_id]:

                admission_criteria = AdmissionCriteria()
                for f in one_criteria['admission_criteria']['admission_criteria']:
                    if f == 'faculty':
                        admission_criteria.faculty = Faculty.objects.get(pk=one_criteria['admission_criteria']['admission_criteria'][f])
                    elif f == 'admission_project':
                        admission_criteria.admission_project = admission_project
                    else:
                        setattr(admission_criteria, f, one_criteria['admission_criteria']['admission_criteria'][f])

                admission_criteria.campus = admission_criteria.faculty.campus
                admission_criteria.save()
                print('+admission_criteria', admission_criteria.id)

                parents = {}
                
                for score_data in one_criteria['admission_criteria']['score_criterias']:
                    score = ScoreCriteria()
                    is_child = False
                    for f in score_data:
                        if f == 'pk':
                            parents[score_data[f]] = score
                            continue
                        if f == 'parent':
                            if score_data[f] != None:
                                #print('parent', score_data, score_data[f], parents[score_data[f]])
                                score.parent = parents[score_data[f]]
                                continue
                        if f == 'value':
                            if score_data[f] != None:
                                score.value = float(score_data[f])
                            else:
                                score.value = None
                            continue
                        if f != 'admission_criteria':
                            setattr(score, f, score_data[f])
                    score.admission_criteria = admission_criteria
                    score.save()

                    #print('+score', score.id, score)

                curriculum_major_admission_criteria = CurriculumMajorAdmissionCriteria()
                curriculum_major_admission_criteria.curriculum_major = curriculum_major
                curriculum_major_admission_criteria.admission_criteria = admission_criteria
                curriculum_major_admission_criteria.slots = one_criteria['slots']
                curriculum_major_admission_criteria.version = 1
                curriculum_major_admission_criteria.save()
                    
                #print('+curriculum_major_admission_criteria', curriculum_major_admission_criteria.id)

if __name__ == '__main__':
    main()

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseForbidden

from majors.models import Faculty, Campus, AdmissionProject, AdmissionRound
from .models import CurriculumMajor, MajorCuptCode, AdmissionCriteria

DEFAULT_CAMPUS_ID = 1

def build_choices(campuses, faculties, current_selection=None):
    choices = []
    for c in campuses:
        is_selected = False
        if current_selection and type(current_selection) == Campus:
            if current_selection.id == c.id:
                is_selected = True
        choices.append({ 'type': 'campus',
                         'obj': c,
                         'id': c.id,
                         'label': c.title,
                         'short_label': c.short_title,
                         'is_selected': is_selected })
        for f in [f for f in faculties if f.campus_id == c.id]:
            is_selected = False
            if current_selection and type(current_selection) == Faculty:
                if current_selection.id == f.id:
                    is_selected = True
            choices.append({ 'type': 'faculty',
                             'obj': f,
                             'id': f.id,
                             'label': f.title,
                             'short_label': f.title,
                             'is_selected': is_selected })

    return choices

def update_campus_keys():
    for c in MajorCuptCode.objects.filter(campus=None).all():
        c.campus = c.faculty.campus
        c.save()
        
    for c in CurriculumMajor.objects.filter(campus=None).all():
        c.campus = c.faculty.campus
        c.save()

def update_project_list():
    codes = MajorCuptCode.objects.all()
    project_sets = {}
    for curriculum_major in CurriculumMajor.objects.all():
        code_id = curriculum_major.cupt_code_id
        if code_id not in project_sets:
            project_sets[code_id] = set()
        project_sets[code_id].add(curriculum_major.admission_project_id)

    for c in codes:
        if c.id not in project_sets:
            pstr = ''
        else:
            pstr = ','.join([str(i) for i in project_sets[c.id]])
            
        c.admission_project_list = pstr
        c.save()
        print(c)


def index(request, campus_id=None, faculty_id=None):
    if campus_id==None and faculty_id==None:
        return redirect(reverse('criteria:index-campus',
                                kwargs={'campus_id':DEFAULT_CAMPUS_ID}))

    #update_campus_keys()
    #update_project_list()
    
    all_campuses = Campus.objects.all()
    all_faculties = Faculty.objects.all()
    all_projects = AdmissionProject.objects.filter(is_available=True).all()

    selected_obj = None

    if faculty_id!=None:
        faculty = get_object_or_404(Faculty, pk=faculty_id)
        campus = faculty.campus
        faculties = [faculty]
        selected_obj = faculty
        selected_label = faculty
        major_codes = MajorCuptCode.objects.filter(faculty=faculty).all()
        curriculum_majors = CurriculumMajor.objects.filter(faculty=faculty).all()
    else:
        campus = get_object_or_404(Campus, pk=campus_id)
        faculties = Faculty.objects.filter(campus=campus).all()
        selected_obj = campus
        selected_label = campus.title
        
        major_codes = MajorCuptCode.objects.filter(campus=campus).order_by('faculty').all()
        curriculum_majors = CurriculumMajor.objects.filter(campus=campus).all()

    selected_project_ids = set()
    for m in major_codes:
        selected_project_ids.update(m.get_admission_project_set())

    selected_projects = [p for p in all_projects
                         if p.id in selected_project_ids]
        
    round_numbers = sorted(set([p.default_round_number for p in selected_projects]))

    choices = build_choices(all_campuses, all_faculties, selected_obj)

    return render(request,
                  'criteria/index.html',
                  { 'choices': choices,
                    'selected_obj': selected_obj,
                    'selected_label': selected_label,
                    'selected_projects': selected_projects,
                    'round_numbers': round_numbers,
                    'campus': campus,
                    'major_codes': major_codes })


def sort_admission_criteria_rows(admission_criteria_rows):
    lst = []
    for criteria in admission_criteria_rows:
        first_criteria = criteria['criterias'][0]
        key = '-'.join([mc.curriculum_major.cupt_code.program_code + mc.curriculum_major.cupt_code.major_code for mc in criteria['majors']])
        total_slots = sum([mc.slots for mc in criteria['majors']])
        lst.append((first_criteria.faculty_id, key, -total_slots, first_criteria.id, criteria))

    return [item[4] for item in sorted(lst)]

def combine_criteria_rows(rows):
    major_slots = {}

    for r in rows:
        curriculum_major_admission_criterias = r['majors']
        for mc in curriculum_major_admission_criterias:
            major = mc.curriculum_major
            major_id = mc.curriculum_major.id
            if major_id not in major_slots:
                major_slots[major_id] = []
            major_slots[major_id].append((mc.slots, mc, r['criterias'][0]))

    combined_rows = []
    deleted_major_ids = set()
            
    for major_id in major_slots:
        slots = major_slots[major_id]
        if len(slots) > 1:
            non_zero_mc = [s for s in slots if s[0] > 0]
            if len(non_zero_mc) == 1:
                combined_rows.append({
                    'majors': [non_zero_mc[0][1]],
                    'criterias': [s[2] for s in slots],
                    'major_count': 1,
                    'criteria_count': len(slots),
                })

                for _,mc,_ in slots:
                    deleted_major_ids.add(mc.id)

    output_rows = []

    for r in rows:
        curriculum_major_admission_criterias = r['majors']
        output_majors = []
        for mc in curriculum_major_admission_criterias:
            if mc.id not in deleted_major_ids:
                output_majors.append(mc)

        if len(output_majors) != 0:
            output_rows.append({
                'majors': output_majors,
                'criterias': r['criterias'],
                'major_count': len(output_majors),
                'criteria_count': len(r['criterias']),
            })

    return output_rows + combined_rows
        
def prepare_admission_criteria(admission_criterias, curriculum_majors, combine_majors=False):
    curriculum_majors_with_criterias = []
    for criteria in admission_criterias:
        criteria.cache_score_criteria_children()
        criteria.curriculum_major_admission_criterias = criteria.curriculummajoradmissioncriteria_set.select_related('curriculum_major').all()
        criteria.curriculum_major_admission_criteria_count = len(criteria.curriculum_major_admission_criterias)
        criteria.curriculum_majors = [mj.curriculum_major for mj in criteria.curriculum_major_admission_criterias]
        curriculum_majors_with_criterias += criteria.curriculum_majors

    curriculum_majors_with_criteria_ids = set([m.id for m
                                               in curriculum_majors_with_criterias])

    free_curriculum_majors = [m for m in curriculum_majors
                              if m.id not in curriculum_majors_with_criteria_ids]

    admission_criteria_rows = [{'majors': c.curriculum_major_admission_criterias,
                                'criterias': [c],
                                'major_count': len(c.curriculum_major_admission_criterias),
                                'criteria_count': len([c])} for c in admission_criterias]

    if combine_majors:
        admission_criteria_rows = combine_criteria_rows(admission_criteria_rows)

    return sort_admission_criteria_rows(admission_criteria_rows), free_curriculum_majors

def get_all_curriculum_majors(project, faculty=None):
    if not faculty:
        majors = CurriculumMajor.objects.filter(
            admission_project_id=project.id).select_related('cupt_code')
    else:
        majors = CurriculumMajor.objects.filter(
            admission_project_id=project.id,
            faculty_id=faculty.id).select_related('cupt_code')

    return majors

def show_project(request, project_id, faculty_id=None):
    project = get_object_or_404(AdmissionProject, pk=project_id)
    if not project.major_detail_visible:
        if not request.user.is_authenticated:
            return HttpResponseForbidden()

    faculties = Faculty.objects.all()
    
    admission_criterias = (AdmissionCriteria
                           .objects
                           .filter(admission_project_id=project_id,
                                   is_deleted=False)
                           .order_by('faculty_id'))

    curriculum_majors = get_all_curriculum_majors(project)
    admission_criteria_rows, free_curriculum_majors = prepare_admission_criteria(admission_criterias, curriculum_majors, True)

    return render(request,
                  'criteria/report_index.html',
                  {'project': project,
                   'admission_criteria_rows': admission_criteria_rows,
                   'free_curriculum_majors': free_curriculum_majors,
                   })

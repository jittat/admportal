from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from majors.models import Faculty, Campus, AdmissionProject, AdmissionRound
from .models import CurriculumMajor, MajorCuptCode

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
        
    choices = build_choices(all_campuses, all_faculties, selected_obj)

    return render(request,
                  'criteria/index.html',
                  { 'choices': choices,
                    'selected_obj': selected_obj,
                    'selected_label': selected_label,
                    'selected_projects': selected_projects,
                    'major_codes': major_codes })

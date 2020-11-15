from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from majors.models import Faculty, Campus
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

def index(request, campus_id=None, faculty_id=None):
    if campus_id==None and faculty_id==None:
        return redirect(reverse('criteria:index-campus',
                                kwargs={'campus_id':DEFAULT_CAMPUS_ID}))

    #update_campus_keys()
    
    all_campuses = Campus.objects.all()
    all_faculties = Faculty.objects.all()

    selected_obj = None
    
    if faculty_id!=None:
        faculty = get_object_or_404(Faculty, pk=faculty_id)
        campus = faculty.campus
        faculties = [faculty]
        selected_obj = faculty

        major_codes = MajorCuptCode.objects.filter(faculty=faculty).all()
        curriculum_majors = CurriculumMajor.objects.filter(faculty=faculty).all()
    else:
        campus = get_object_or_404(Campus, pk=campus_id)
        faculties = Faculty.objects.filter(campus=campus).all()
        selected_obj = campus

        major_codes = MajorCuptCode.objects.filter(campus=campus).order_by('faculty').all()
        curriculum_majors = CurriculumMajor.objects.filter(campus=campus).all()

    choices = build_choices(all_campuses, all_faculties, selected_obj)

    return render(request,
                  'criteria/index.html',
                  { 'choices': choices,
                    'major_codes': major_codes })

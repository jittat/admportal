from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect

from django.conf import settings

from .models import AdmissionProject, Major

def index(request):
    if not request.user.is_authenticated:
        return redirect(reverse('main-index'))
        
    projects = AdmissionProject.objects.all()

    return render(request,
                  'majors/index.html',
                  { 'projects': projects })


def extract_and_attach_major_comments(majors):
    comment_number = 0
    comments = []
    comment_map = {}
    for m in majors:
        if m.slots_comments != '':
            if m.slots_comments not in comment_map:
                comment_number += 1
                comment_map[m.slots_comments] = comment_number
                comments.append(m.slots_comments)
            m.comment_number = comment_map[m.slots_comments]
    return comments


def search_majors(request):
    if not settings.ALLOW_SEARCH:
        return redirect(reverse('main-index'))
    
    query = request.POST['query'].strip()
    if query == '':
        return redirect(reverse('main-index'))

    visible_projects = AdmissionProject.objects.filter(major_detail_visible=True).all()
    visible_project_ids = set([p.id for p in visible_projects])
    
    search_query = Major.simplify_title(query)
    majors = [m for m in Major.objects.filter(simplified_title__contains=search_query).order_by('admission_project_id')
              if m.admission_project_id in visible_project_ids]

    found_projects = {}
    projects = []
    for m in majors:
        if m.admission_project_id not in found_projects:
            found_projects[m.admission_project_id] = m.admission_project
            projects.append(m.admission_project)
            p = m.admission_project
            p.found_majors = []
        else:
            p = found_projects[m.admission_project_id]

        p.found_majors.append(m)


    for p in projects:
        p.comments = extract_and_attach_major_comments(p.found_majors)
        
    scope_display = settings.SEARCH_SCOPE_DISPLAY
    empty_display_message = settings.SEARCH_EMPTY_DISPLAY_MESSAGE

    return render(request,
                  'majors/search.html',
                  { 'projects': projects,
                    'query': query,
                    'scope_display': scope_display,
                    'empty_display_message': empty_display_message })


def list_majors(request, project_id):
    project = get_object_or_404(AdmissionProject, pk=project_id)

    if (not project.major_detail_visible) and (not request.user.is_authenticated):
        return redirect(reverse('main-index'))
    
    majors = project.major_set.all()

    comments = extract_and_attach_major_comments(majors)
    
    return render(request,
                  'majors/majors.html',
                  { 'project': project,
                    'majors': majors,
                    'comments': comments })


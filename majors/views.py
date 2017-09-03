from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect

from .models import AdmissionProject

def index(request):
    if not request.user.is_authenticated:
        return redirect(reverse('main-index'))
        
    projects = AdmissionProject.objects.all()

    return render(request,
                  'majors/index.html',
                  { 'projects': projects })

    
def list_majors(request, project_id):
    project = get_object_or_404(AdmissionProject, pk=project_id)

    if (not project.major_detail_visible) and (not request.user.is_authenticated):
        return redirect(reverse('main-index'))
    
    majors = project.major_set.all()

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
    
    return render(request,
                  'majors/majors.html',
                  { 'project': project,
                    'majors': majors,
                    'comments': comments })


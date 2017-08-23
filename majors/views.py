from django.shortcuts import render, get_object_or_404

from .models import AdmissionProject

def index(request):
    projects = AdmissionProject.objects.all()

    return render(request,
                  'majors/index.html',
                  { 'projects': projects })

    
def list_majors(request, project_id):
    project = get_object_or_404(AdmissionProject, pk=project_id)
    majors = project.major_set.all()
    
    return render(request,
                  'majors/majors.html',
                  { 'project': project,
                    'majors': majors })


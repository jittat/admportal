from django.shortcuts import render

from majors.models import Campus, AdmissionRound, AdmissionProject

def index(request):
    admission_rounds = AdmissionRound.objects.all()
    campuses = Campus.objects.all()
    
    return render(request,
                  'main/index.html',
                  { 'admission_rounds': admission_rounds,
                    'campuses': campuses, })

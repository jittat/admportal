from django.shortcuts import render

from majors.models import Campus, AdmissionRound, AdmissionProject

from django.conf import settings

from .models import Announcement


def index(request):
    admission_rounds = AdmissionRound.objects.all()
    campuses = Campus.objects.all()

    announcements = Announcement.objects.filter(is_published=True).all()

    allow_search = settings.ALLOW_SEARCH
    
    return render(request,
                  'main/index.html',
                  { 'admission_rounds': admission_rounds,
                    'campuses': campuses,
                    'announcements': announcements,
                    'allow_search': allow_search })

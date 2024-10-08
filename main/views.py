from django.shortcuts import render

from majors.models import Campus, AdmissionRound, AdmissionProject

from django.conf import settings

from .models import Announcement

DEFAULT_ROUND_NUMBER = Announcement.DEFAULT_ROUND_NUMBER

def index(request):
    admission_rounds = AdmissionRound.objects.all()
    campuses = Campus.objects.all()

    announcements = Announcement.objects.filter(is_published=True).all()

    all_rounds = []
    all_announcement_rounds = {}
    announcement_rounds = []

    for a in announcements:
        if a.admission_round:
            round_number = a.admission_round.number
            if round_number not in all_announcement_rounds:
                all_rounds.append(round_number)
                all_announcement_rounds[round_number] = []

    for a in announcements:
        if a.admission_round:
            round_number = a.admission_round.number
            all_announcement_rounds[round_number].append(a)
        else:
            for round_number in all_rounds:
                all_announcement_rounds[round_number].append(a)

    for r in sorted(all_rounds):
        announcement_rounds.append({'number': r,
                                    'items': all_announcement_rounds[r]})

    allow_search = settings.ALLOW_SEARCH

    projects = AdmissionProject.objects.filter(major_detail_visible=True).order_by('default_round_number','display_rank').all()

    for p in projects:
        if p.campus != None:
            p.campuses = [p.campus]
    
    return render(request,
                  'main/index.html',
                  { 'admission_rounds': admission_rounds,
                    'campuses': campuses,
                    'announcements': announcements,
                    'announcement_rounds': announcement_rounds,
                    'default_round_number': DEFAULT_ROUND_NUMBER,
                    'admission_projects': projects,
                    'allow_search': allow_search })

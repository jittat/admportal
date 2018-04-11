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
    
    return render(request,
                  'main/index.html',
                  { 'admission_rounds': admission_rounds,
                    'campuses': campuses,
                    'announcements': announcements,
                    'announcement_rounds': announcement_rounds,
                    'default_round_number': DEFAULT_ROUND_NUMBER,
                    'allow_search': allow_search })

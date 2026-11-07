from django.shortcuts import render

from majors.models import Campus, AdmissionRound, AdmissionProject

from django.conf import settings

from .models import Announcement, Banner


def pick_default_round_number(announcement_rounds, announcements):
    """Round number of the announcement tab to open first.

    The round checked as is_default_tab in the admin, if it has a tab;
    otherwise the round of the most recent announcement that has a round.
    None when there is no round tab at all.
    """
    tab_numbers = {r['number'] for r in announcement_rounds}

    chosen = AdmissionRound.objects.filter(is_default_tab=True).first()
    if chosen and chosen.number in tab_numbers:
        return chosen.number

    with_round = [a for a in announcements if a.admission_round]
    if not with_round:
        return None
    latest = max(with_round, key=lambda a: a.created_date)
    return latest.admission_round.number


def index(request):
    admission_rounds = AdmissionRound.objects.all()
    campuses = Campus.objects.all()

    announcements = (Announcement.objects
                     .filter(is_published=True)
                     .select_related('admission_round'))

    # Random pick among visible banners; may become a slideshow later.
    banner = Banner.objects.filter(is_hidden=False).order_by('?').first()

    all_rounds = []
    all_announcement_rounds = {}
    round_titles = {}
    announcement_rounds = []

    for a in announcements:
        if a.admission_round:
            round_number = a.admission_round.number
            if round_number not in all_announcement_rounds:
                all_rounds.append(round_number)
                all_announcement_rounds[round_number] = []
                round_titles[round_number] = a.admission_round.number_title

    for a in announcements:
        if a.admission_round:
            round_number = a.admission_round.number
            all_announcement_rounds[round_number].append(a)
        else:
            for round_number in all_rounds:
                all_announcement_rounds[round_number].append(a)

    for r in sorted(all_rounds):
        announcement_rounds.append({'number': r,
                                    'title': round_titles[r],
                                    'items': all_announcement_rounds[r]})

    default_round_number = pick_default_round_number(announcement_rounds,
                                                     announcements)

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
                    'banner': banner,
                    'announcement_rounds': announcement_rounds,
                    'default_round_number': default_round_number,
                    'admission_projects': projects,
                    'allow_search': allow_search })

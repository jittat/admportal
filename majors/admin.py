from django.contrib import admin

from .models import Campus, Faculty, AdmissionRound, AdmissionProject, Major

admin.site.register(Campus)
admin.site.register(Faculty)
admin.site.register(AdmissionRound)
admin.site.register(AdmissionProject)
admin.site.register(Major)

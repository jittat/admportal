from django.contrib import admin

from .models import Campus, Faculty, AdmissionRound, AdmissionProject, Major

def make_available(modeladmin, request, queryset):
    for project in queryset:
        project.is_available = True
        project.save()
make_available.short_description = 'Mark selected project as available'

def make_major_visible(modeladmin, request, queryset):
    for project in queryset:
        project.major_detail_visible = True
        project.save()
make_major_visible.short_description = 'Show major details'

class AdmissionProjectAdmin(admin.ModelAdmin):
    list_display = ['title',
                    'campus',
                    'is_available',
                    'major_detail_visible']
    ordering = ['id']
    actions = [make_available, make_major_visible]

admin.site.register(AdmissionProject, AdmissionProjectAdmin)

admin.site.register(Campus)
admin.site.register(Faculty)
admin.site.register(AdmissionRound)
admin.site.register(Major)

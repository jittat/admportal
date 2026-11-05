from django.contrib import admin
from django.utils.html import format_html

from .models import Announcement, Banner

admin.site.register(Announcement)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['thumbnail', '__str__', 'link_url', 'is_hidden', 'rank', 'created_date']
    list_display_links = ['thumbnail', '__str__']
    list_editable = ['is_hidden', 'rank']
    list_filter = ['is_hidden']

    @admin.display(description='ภาพ')
    def thumbnail(self, obj):
        if not obj.image:
            return ''
        return format_html('<img src="{}" style="max-height: 60px;" />', obj.image.url)

from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def current_year():
    return settings.ADMISSION_YEAR

@register.simple_tag
def admission_round_count():
    return settings.ADMISSION_ROUND_COUNT






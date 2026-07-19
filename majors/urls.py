from django.urls import re_path

from . import views

app_name = 'org-majors'
urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^projects/(\d+)/$', views.list_majors, name='list-majors'),
    re_path(r'^search/$', views.search_majors, name='search-majors'),
]

# from django.conf.urls import url
from django.urls import path

from . import views

app_name = 'org-majors'
urlpatterns = [
    path('', views.index, name='index'),
    path('projects/<int:id>/', views.list_majors, name='list-majors'),
    path('search/', views.search_majors, name='search-majors'),
]

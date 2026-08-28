from django.urls import path

from . import views

app_name = 'criteria'
urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search_majors, name='search-majors'),
    path('campus/<int:campus_id>/', views.index, name='index-campus'),
    path('faculty/<int:faculty_id>/', views.index, name='index-faculty'),
    path('project/<int:project_id>/', views.show_project, name='project-index'),
    path('project/<int:project_id>/<int:faculty_id>/', views.show_project, name='project-faculty'),
]

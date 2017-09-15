from django.conf.urls import url

from . import views

app_name = 'majors'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^projects/(\d+)/$', views.list_majors, name='list-majors'),
    url(r'^search/$', views.search_majors, name='search-majors'),
]

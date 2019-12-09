from django.urls import path
from . import views

app_name = 'search'
urlpatterns = [
    path('volume/', views.SelectYearView, name='SelectYear'),
    path('no/<int:id>/', views.SelectNoView, name='SelectNo'),
    path('detail/', views.SearchDetailView, name='SearchDetail'),
]

from django.urls import path
from . import views

app_name = 'search'
# 巻号選択、詳細検索、著作権案内のURLを公開する。
urlpatterns = [
    path('volume/', views.SelectYearView, name='SelectYear'),
    path('no/<int:year_id>/', views.SelectNoView, name='SelectNo'),
    path('detail/', views.SearchDetailView, name='SearchDetail'),
    path('copyright/', views.CopyrightView, name='Copyright'),
]

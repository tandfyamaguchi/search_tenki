"""プロジェクトのURL設定。"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('list/', include('list.urls', namespace='list')),
    path('search/', include('search.urls', namespace='search')),
    path('', include('home.urls', namespace='home')),
    path('admin/', admin.site.urls),
]

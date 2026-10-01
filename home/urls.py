from django.urls import path
from . import views

app_name = 'home'
# トップ画面へのURLを名前付きで公開する。
urlpatterns = [
    path('', views.HomeView, name='home'),
]

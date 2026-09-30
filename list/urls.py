from django.urls import path
from . import views

app_name = 'list'
urlpatterns = [
    path('list1/<int:id>/', views.ShowListView1, name='ShowList1'),
    path('list2/', views.ShowListView2, name='ShowList2'),
    path('list3/<int:id>/<int:shurui>/', views.ShowListView3, name='ShowList3'),
]

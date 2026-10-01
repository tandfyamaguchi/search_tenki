from django.urls import path
from . import views

app_name = 'list'
# 巻号一覧、詳細検索結果、関連項目一覧のURLを公開する。
urlpatterns = [
    path('list1/<int:id>/', views.ShowListView1, name='ShowList1'),
    path('list2/', views.ShowListView2, name='ShowList2'),
    path('list3/<int:id>/<int:shurui>/', views.ShowListView3, name='ShowList3'),
]

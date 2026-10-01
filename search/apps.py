from django.apps import AppConfig


# 発行管理と公開検索を提供するアプリの設定を定義する。
class SearchConfig(AppConfig):
    name = 'search'
    verbose_name = '発行管理'

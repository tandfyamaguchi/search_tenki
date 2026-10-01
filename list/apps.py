from django.apps import AppConfig


# 記事と関連マスタを管理するアプリの設定を定義する。
class ListConfig(AppConfig):
    name = 'list'
    verbose_name = '記事管理'

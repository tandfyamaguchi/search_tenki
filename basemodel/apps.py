from django.apps import AppConfig


# 旧DBを参照するbasemodelアプリをDjangoへ登録する。
class BasemodelConfig(AppConfig):
    name = 'basemodel'

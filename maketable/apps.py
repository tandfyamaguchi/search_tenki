from django.apps import AppConfig


# 初回導入専用の管理コマンドをDjangoへ登録する。
class MaketableConfig(AppConfig):
    name = 'maketable'
    verbose_name = '初回データ投入'

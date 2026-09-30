#データベースを使い分ける
class DBRouter:
    # モデルごとの読み込み先データベースを返す。
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return 'etenki'
        else:
            return 'default'

    # モデルごとの書き込み先データベースを返す。
    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return False
        else:
            return 'default'

    # データベースをまたぐモデル間の関連を許可する。
    def allow_relation(self, obj1, obj2, **hints):
        return True

    # basemodelのマイグレーションを実行しない。
    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == 'basemodel':
            return False
        else:
            return 'default'

# データベースを使い分ける。
class DBRouter:
    # モデルごとの読み込み先データベースを返す。
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return 'etenki'
        return 'default'

    # 旧DBモデルの書込み先も、読み取り専用の旧DBにする。
    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return 'etenki'
        return 'default'

    # データベースをまたぐモデル間の関連を許可する。
    def allow_relation(self, obj1, obj2, **hints):
        return True

    # 運用DBだけに通常のmigrationを適用し、旧DBには一切適用しない。
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db != 'default':
            return False
        return app_label != 'basemodel'

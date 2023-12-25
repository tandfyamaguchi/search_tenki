#データベースを使い分ける
import random
class DBRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return 'etenki'
        else:
            return 'default'
        return None


    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'basemodel':
            return False
        else:
            return 'default'
        return None
 
    def allow_relation(self, obj1, obj2, **hints):
        return True
 
    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == 'basemodel':
            return False
        else:
            return 'default'
        return None
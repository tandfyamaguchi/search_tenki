from django.conf import settings
from django.test import SimpleTestCase

from .db_router import DBRouter
from . import settings as project_settings


# 旧DBへのmigrationを拒否するDBルーターの設定を確認する。
class DBRouterMigrationTests(SimpleTestCase):
    # 各テストで同じDBルーターを使用する。
    def setUp(self):
        self.router = DBRouter()

    # 通常モデルは運用DBだけでmigrationできる。
    def test_regular_models_can_migrate_only_on_default_database(self):
        self.assertIs(self.router.allow_migrate('default', 'list'), True)
        self.assertIs(self.router.allow_migrate('etenki', 'list'), False)

    # 旧DBの読み取りモデルは、どのDBにもmigrationしない。
    def test_basemodel_cannot_migrate_on_any_database(self):
        self.assertIs(self.router.allow_migrate('default', 'basemodel'), False)
        self.assertIs(self.router.allow_migrate('etenki', 'basemodel'), False)


# 旧DBが接続設定でも書込み不能であることを確認する。
class LegacyDatabaseSettingsTests(SimpleTestCase):
    # 実運用の旧DBにはSQLiteの読み取り専用URIを使う。
    def test_legacy_database_uses_read_only_sqlite_uri(self):
        database = settings.DATABASES['etenki']

        self.assertTrue(database['OPTIONS']['uri'])
        self.assertTrue(project_settings.LEGACY_DATABASE_URI.endswith('?mode=ro'))

    # テスト時だけは旧DBを模した書込み可能なメモリDBを使う。
    def test_legacy_database_uses_memory_database_for_tests(self):
        test_database = settings.DATABASES['etenki']['TEST']['NAME']

        self.assertIn('mode=memory', test_database)

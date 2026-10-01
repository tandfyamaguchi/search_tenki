from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .services.legacy_sync import LegacySynchronizer


# 初回同期でカテゴリを自動作成しない事前検証を確認する。
class LegacySynchronizerCategoryValidationTests(SimpleTestCase):
    # 原稿種別付きで未登録カテゴリを準備するよう、同期前に明示して停止する。
    def test_unknown_category_is_rejected_before_synchronization(self):
        synchronizer = LegacySynchronizer()

        with self.assertRaisesMessage(CommandError, '原稿種別付きで登録してください'):
            synchronizer._validate_category_names(
                {'旧DBだけにあるカテゴリ'},
                {'既存カテゴリ': object()},
            )

    # 承認済みベースDBに登録済みのカテゴリは、そのまま同期に進める。
    def test_registered_categories_are_accepted_before_synchronization(self):
        synchronizer = LegacySynchronizer()

        synchronizer._validate_category_names(
            {'既存カテゴリ'},
            {'既存カテゴリ': object()},
        )

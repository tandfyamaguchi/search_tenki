from django.core.management.base import BaseCommand, CommandError

from list.models import Category
from search.category_groups import MANUSCRIPT_TYPE_CATEGORY_LOOKUP


# 分類設定のIDとDBのカテゴリIDを比較して不一致を返す。
def find_category_group_errors(database_categories):
    configured_ids = set(MANUSCRIPT_TYPE_CATEGORY_LOOKUP)
    database_names = {
        category.id: category.name for category in database_categories
    }
    database_ids = set(database_names)
    comment_ids = set(comment_names)
    errors = []

    for category_id in sorted(database_ids - configured_ids):
        errors.append(
            f'DBのカテゴリID {category_id}（{database_names[category_id]}）が'
            '原稿種別に登録されていません。'
        )
    for category_id in sorted(configured_ids - database_ids):
        errors.append(
            f'原稿種別に登録されたカテゴリID {category_id} がDBにありません。'
        )

    return errors


# カテゴリ分類設定をDBと照合する読み取り専用コマンド。
class Command(BaseCommand):
    help = 'カテゴリ分類のIDをDBのカテゴリIDと照合します。'

    # 不一致があれば終了コード付きの設定エラーとして通知する。
    def handle(self, *args, **options):
        database_categories = Category.objects.order_by('id')
        errors = find_category_group_errors(database_categories)

        if errors:
            raise CommandError(
                'カテゴリ分類設定がDBと一致しません。\n- '
                + '\n- '.join(errors)
            )

        self.stdout.write(
            self.style.SUCCESS(
                'カテゴリ分類IDはDBと一致しています'
                f'（{len(MANUSCRIPT_TYPE_CATEGORY_LOOKUP)}件）。'
            )
        )

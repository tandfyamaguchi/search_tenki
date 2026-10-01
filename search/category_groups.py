# 詳細検索で使う、DB管理の原稿種別データを整形する。
from django.core.exceptions import ImproperlyConfigured

from list.models import CategoryGroup


# 現在のカテゴリを、DBの原稿種別ごとのテンプレート用データへ整形する。
def build_category_groups(categories, selected_category_ids=()):
    selected_ids = {str(category_id) for category_id in selected_category_ids}
    categories_by_group_id = {}

    for category in categories:
        if category.group_id is None:
            # DB制約の適用漏れを、公開画面で分かる設定エラーとして通知する。
            raise ImproperlyConfigured(
                '原稿種別が未指定のカテゴリがあります: '
                f'{category.id}（{category.name}）'
            )
        categories_by_group_id.setdefault(category.group_id, []).append({
            'id': category.id,
            'input_id': f'id_categ_{category.id}',
            'name': category.name,
            'selected': str(category.id) in selected_ids,
        })

    groups = []
    for group in CategoryGroup.objects.order_by('display_order', 'id'):
        groups.append({
            'categories': categories_by_group_id.pop(group.id, []),
            'child_list_id': f'category-group-children-{group.pk}',
            'input_id': f'category-group-{group.pk}',
            'name': group.name,
        })

    if categories_by_group_id:
        # 削除済みの原稿種別を参照するデータは、詳細検索を続けるより先に通知する。
        unexpected_group_ids = sorted(
            categories_by_group_id
        )
        raise ImproperlyConfigured(
            '存在しない原稿種別を参照するカテゴリがあります: '
            + ', '.join(str(group_id) for group_id in unexpected_group_ids)
        )

    return groups

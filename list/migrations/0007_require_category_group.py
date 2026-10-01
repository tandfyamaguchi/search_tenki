# カテゴリの原稿種別をDB制約で必須にする。
import django.db.models.deletion
from django.db import migrations, models


MAX_DISPLAYED_CATEGORIES = 20


# 原稿種別が未指定のカテゴリを示し、制約の適用前に安全に停止する。
def reject_unassigned_categories(apps, schema_editor):
    Category = apps.get_model('list', 'Category')
    database_alias = schema_editor.connection.alias
    unassigned_categories = (
        Category.objects.using(database_alias)
        .filter(group__isnull=True)
        .order_by('id')
    )
    unassigned_count = unassigned_categories.count()
    if not unassigned_count:
        return

    displayed_categories = list(
        unassigned_categories.values_list('id', 'name')[:MAX_DISPLAYED_CATEGORIES]
    )
    displayed_text = ', '.join(
        f'カテゴリID {category_id}（{name}）'
        for category_id, name in displayed_categories
    )
    remaining_count = unassigned_count - len(displayed_categories)
    if remaining_count:
        displayed_text += f' ほか{remaining_count}件'
    raise RuntimeError(
        '原稿種別が未指定のカテゴリがあるため、カテゴリの所属を必須にできません。'
        f'対象: {displayed_text}'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('list', '0006_category_group_admin'),
    ]

    operations = [
        migrations.RunPython(
            reject_unassigned_categories,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='category',
            name='group',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='categories',
                to='list.categorygroup',
            ),
        ),
    ]

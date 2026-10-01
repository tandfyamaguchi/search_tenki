# カテゴリの原稿種別をDB管理へ移し、既存のID対応を引き継ぐ。
import django.db.models.deletion
from django.db import migrations, models


# 初回移行だけで使う、承認済み旧カテゴリIDと原稿種別の対応を固定する。
# 履歴migrationを将来の通常モジュール変更から独立させるため、ここで保持する。
INITIAL_MANUSCRIPT_TYPE_CATEGORY_GROUPS = (
    ('論文', (192,)),
    ('短報', (161,)),
    ('解説', (184,)),
    ('調査ノート', (190,)),
    ('シンポジウム', (23,)),
    ('研究会報告', (162,)),
    ('最近の学術動向', (139,)),
    ('天気の教室', (48,)),
    ('気象談話室', (151,)),
    ('新用語解説', (128, 160)),
    ('質疑応答', (199, 200)),
    ('海外だより', (154,)),
    ('気象業務の窓', (149,)),
    ('学位論文紹介', (1, 106)),
    ('本だな', (138, 143)),
    ('会員の広場', (29, 30)),
    ('日々の天気図', (129,)),
    ('今月のひまわり画像', (28, 130, 131)),
    ('気候情報', (25, 146)),
    ('情報の広場', (117,)),
    ('新刊図書案内', (124, 125, 126)),
    (
        '学会だより',
        (
            49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
            63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76,
            77, 78, 79, 80, 81, 82, 83, 84,
        ),
    ),
    ('支部だより', (42, 43, 44, 45, 121, 122, 123)),
    ('情報 File', (32, 113, 114, 115, 116)),
    (
        'その他',
        (
            2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
            18, 19, 20, 21, 22, 24, 26, 27, 31, 33, 34, 35, 36, 37,
            38, 39, 40, 41, 46, 47, 85, 86, 87, 88, 89, 90, 91, 92,
            93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
            107, 108, 109, 110, 111, 112, 118, 119, 120, 127, 132, 133,
            134, 135, 136, 137, 140, 141, 142, 144, 145, 147, 148, 150,
            152, 153, 155, 156, 157, 158, 159, 163, 164, 165, 166, 167,
            168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179,
            180, 181, 182, 183, 185, 186, 187, 188, 189, 191, 193, 194,
            195, 196, 197, 198, 201, 202, 203, 204, 205, 206,
        ),
    ),
)


# 既存カテゴリIDと初期原稿種別の対応を検証して、DBへ登録する。
def populate_category_groups(apps, schema_editor):
    Category = apps.get_model('list', 'Category')
    CategoryGroup = apps.get_model('list', 'CategoryGroup')
    category_ids_by_group_name = {}
    configured_category_ids = set()

    for position, (group_name, category_ids) in enumerate(
        INITIAL_MANUSCRIPT_TYPE_CATEGORY_GROUPS,
        start=1,
    ):
        if group_name in category_ids_by_group_name:
            raise RuntimeError(f'原稿種別「{group_name}」が重複しています。')
        category_ids_by_group_name[group_name] = tuple(category_ids)
        for category_id in category_ids:
            if category_id in configured_category_ids:
                raise RuntimeError(
                    f'カテゴリID {category_id} が複数の原稿種別に登録されています。'
                )
            configured_category_ids.add(category_id)

    existing_category_ids = set(
        Category.objects.using(schema_editor.connection.alias).values_list(
            'id',
            flat=True,
        )
    )
    if existing_category_ids and existing_category_ids != configured_category_ids:
        missing_ids = sorted(configured_category_ids - existing_category_ids)
        unexpected_ids = sorted(existing_category_ids - configured_category_ids)
        raise RuntimeError(
            '既存カテゴリIDと初期原稿種別の対応が一致しません。'
            f'不足: {missing_ids[:20]}; 想定外: {unexpected_ids[:20]}'
        )

    groups_by_name = {}
    for position, (group_name, _category_ids) in enumerate(
        INITIAL_MANUSCRIPT_TYPE_CATEGORY_GROUPS,
        start=1,
    ):
        category_group, created = CategoryGroup.objects.using(
            schema_editor.connection.alias
        ).get_or_create(
            name=group_name,
            defaults={'display_order': position},
        )
        if not created and category_group.display_order != position:
            raise RuntimeError(
                f'原稿種別「{group_name}」の表示順が初期値と一致しません。'
            )
        groups_by_name[group_name] = category_group

    for group_name, category_ids in category_ids_by_group_name.items():
        Category.objects.using(schema_editor.connection.alias).filter(
            id__in=category_ids
        ).update(group_id=groups_by_name[group_name].pk)


class Migration(migrations.Migration):

    dependencies = [
        ('list', '0005_article_author_display_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoryGroup',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100, unique=True)),
                (
                    'display_order',
                    models.PositiveSmallIntegerField(unique=True),
                ),
            ],
            options={
                'verbose_name': '原稿種別',
                'verbose_name_plural': '原稿種別',
                'ordering': ('display_order', 'id'),
            },
        ),
        migrations.AddField(
            model_name='category',
            name='group',
            field=models.ForeignKey(
                blank=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='categories',
                to='list.categorygroup',
            ),
        ),
        migrations.AlterField(
            model_name='kijis',
            name='category',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='category',
                to='list.category',
            ),
        ),
        migrations.RunPython(populate_category_groups, migrations.RunPython.noop),
    ]

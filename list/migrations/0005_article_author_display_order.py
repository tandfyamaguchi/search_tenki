# 既存の著者中間テーブルを、表示順を持つ明示的な中間モデルへ移行する。
from django.db import migrations, models
import django.db.models.deletion


DISPLAY_ORDER_FIELD_NAME = 'display_order'
BATCH_SIZE = 1000


# 自動生成された中間テーブルへ、表示順の列だけを追加する。
def add_display_order_column(apps, schema_editor):
    Kijis = apps.get_model('list', 'Kijis')
    through_model = Kijis._meta.get_field('author').remote_field.through
    display_order = models.PositiveSmallIntegerField(default=0)
    display_order.set_attributes_from_name(DISPLAY_ORDER_FIELD_NAME)
    schema_editor.add_field(through_model, display_order)


# 逆移行では、追加した表示順の列だけを元に戻す。
def remove_display_order_column(apps, schema_editor):
    Kijis = apps.get_model('list', 'Kijis')
    through_model = Kijis._meta.get_field('author').remote_field.through
    display_order = models.PositiveSmallIntegerField(default=0)
    display_order.set_attributes_from_name(DISPLAY_ORDER_FIELD_NAME)
    schema_editor.remove_field(through_model, display_order)


# 既存の登録順を、記事ごとの1始まりの公開表示順として保存する。
def populate_display_order(apps, schema_editor):
    ArticleAuthor = apps.get_model('list', 'ArticleAuthor')
    database_alias = schema_editor.connection.alias
    rows_to_update = []
    current_article_id = None
    display_order = 0

    for relation in ArticleAuthor.objects.using(database_alias).order_by(
        'kijis_id',
        'id',
    ).iterator():
        if relation.kijis_id != current_article_id:
            current_article_id = relation.kijis_id
            display_order = 0
        display_order += 1
        relation.display_order = display_order
        rows_to_update.append(relation)

        if len(rows_to_update) >= BATCH_SIZE:
            ArticleAuthor.objects.using(database_alias).bulk_update(
                rows_to_update,
                [DISPLAY_ORDER_FIELD_NAME],
                batch_size=BATCH_SIZE,
            )
            rows_to_update = []

    if rows_to_update:
        ArticleAuthor.objects.using(database_alias).bulk_update(
            rows_to_update,
            [DISPLAY_ORDER_FIELD_NAME],
            batch_size=BATCH_SIZE,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('list', '0004_alter_author_options_alter_bunrui_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            add_display_order_column,
            remove_display_order_column,
        ),
        # DB上の既存テーブルを保ったまま、ORMの中間モデル定義だけを切り替える。
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='ArticleAuthor',
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
                        (
                            'display_order',
                            models.PositiveSmallIntegerField(default=0),
                        ),
                        (
                            'author',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name='article_author_links',
                                to='list.author',
                            ),
                        ),
                        (
                            'kijis',
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name='author_links',
                                to='list.kijis',
                            ),
                        ),
                    ],
                    options={
                        'verbose_name': '記事の著者',
                        'verbose_name_plural': '記事の著者',
                        'ordering': ('display_order', 'id'),
                        'db_table': 'list_kijis_author',
                    },
                ),
                migrations.AlterField(
                    model_name='kijis',
                    name='author',
                    field=models.ManyToManyField(
                        blank=True,
                        related_name='author',
                        through='list.ArticleAuthor',
                        through_fields=('kijis', 'author'),
                        to='list.author',
                    ),
                ),
            ],
        ),
        migrations.RunPython(populate_display_order, migrations.RunPython.noop),
    ]

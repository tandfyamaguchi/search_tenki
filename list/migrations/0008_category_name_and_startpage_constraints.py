# カテゴリ名の重複と記事開始頁の負数を防ぐ。

from django.db import migrations, models


# カテゴリ名と記事開始頁にDBの入力制約を適用する。
class Migration(migrations.Migration):

    dependencies = [
        ('list', '0007_require_category_group'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='kijis',
            name='startpage',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]

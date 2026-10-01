# 巻・号の数値項目で負数を保存できないようにする。

from django.db import migrations, models


# 巻・号の数値項目を非負の整数へ変更する。
class Migration(migrations.Migration):

    dependencies = [
        ('search', '0005_volume_issue_admin_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='year',
            name='year',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name='year',
            name='volume',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name='month',
            name='no',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name='month',
            name='start_page',
            field=models.PositiveSmallIntegerField(),
        ),
    ]

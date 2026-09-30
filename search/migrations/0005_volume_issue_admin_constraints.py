# 巻・号の識別名と重複登録を防ぐ制約を追加する。

from django.db import migrations, models


# 巻・号の管理用メタデータと一意制約を適用する。
class Migration(migrations.Migration):

    dependencies = [
        ('search', '0004_alter_month_id_alter_year_id'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='month',
            options={
                'verbose_name': '号',
                'verbose_name_plural': '号',
            },
        ),
        migrations.AlterModelOptions(
            name='year',
            options={
                'verbose_name': '巻',
                'verbose_name_plural': '巻',
            },
        ),
        migrations.AddConstraint(
            model_name='month',
            constraint=models.UniqueConstraint(
                fields=('volume', 'no'),
                name='search_month_unique_volume_no',
                violation_error_message='同じ巻に同じ号は登録できません。',
            ),
        ),
        migrations.AddConstraint(
            model_name='year',
            constraint=models.UniqueConstraint(
                fields=('volume',),
                name='search_year_unique_volume',
                violation_error_message='同じ巻番号が既に登録されています。',
            ),
        ),
    ]

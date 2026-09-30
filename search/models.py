from django.db import models

# 巻と発行年を管理する。
class Year(models.Model):
    year = models.SmallIntegerField()
    volume = models.SmallIntegerField()

    # 検索フォームの既存表示形式として巻番号を返す。
    def __str__(self):
        return str(self.volume)

    # 管理画面の名称と巻番号の重複禁止を定義する。
    class Meta:
        verbose_name = '巻'
        verbose_name_plural = '巻'
        constraints = [
            models.UniqueConstraint(
                fields=('volume',),
                name='search_year_unique_volume',
                violation_error_message='同じ巻番号が既に登録されています。',
            ),
        ]


# 巻に属する号と開始頁を管理する。
class Month(models.Model):
    volume = models.ForeignKey(Year, on_delete=models.PROTECT)
    no = models.SmallIntegerField()
    start_page = models.SmallIntegerField()

    # 検索フォームの既存表示形式として号番号を返す。
    def __str__(self):
        return str(self.no)

    # 管理画面の名称と同一巻内での号番号の重複禁止を定義する。
    class Meta:
        verbose_name = '号'
        verbose_name_plural = '号'
        constraints = [
            models.UniqueConstraint(
                fields=('volume', 'no'),
                name='search_month_unique_volume_no',
                violation_error_message='同じ巻に同じ号は登録できません。',
            ),
        ]

from django.db import models

#年検索、詳細検索のフォーム作成で使用(Monthで参照)
class Year(models.Model):
    year = models.SmallIntegerField()
    volume = models.SmallIntegerField()

    def __str__(self):
        return str(self.volume)

#No検索表示、詳細検索のフォーム作成で使用
class Month(models.Model):
    volume = models.ForeignKey(Year, on_delete=models.PROTECT)
    no = models.SmallIntegerField()
    start_page = models.SmallIntegerField()

    def __str__(self):
        return str(self.no)
 
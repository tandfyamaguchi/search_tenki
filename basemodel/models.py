from django.db import models

class Kiji(models.Model):
    bunrui = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    title_jp = models.CharField(max_length=400, blank=True, null=True)
    author_jp = models.CharField(max_length=256, blank=True, null=True)
    volume = models.TextField(blank=True, null=True)  # This field type is a guess.
    start_page = models.SmallIntegerField(blank=True, null=True)
    no = models.TextField(blank=True, null=True)  # This field type is a guess.
    keyword = models.CharField(max_length=256, blank=True, null=True)
    pdf = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'kiji'


class Naiyou(models.Model):
    title = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'naiyou'

    def __str__(self):
        return str(self.title)

from django.db import models

class Year(models.Model):
    year = models.SmallIntegerField()
    volume = models.SmallIntegerField()

    def __str__(self):
        return str(self.volume)

class Month(models.Model):
    volume = models.ForeignKey(Year, on_delete=models.PROTECT)
    no = models.SmallIntegerField()
    start_page = models.SmallIntegerField()

    def __str__(self):
        return str(self.no)
 
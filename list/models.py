from django.db import models   

class Bunrui(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)


class Author(models.Model):
    name = models.CharField(max_length=256)

    def __str__(self):
        return str(self.name)


class Keyword(models.Model):
    name = models.CharField(max_length=256)

    def __str__(self):
        return str(self.name)


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)


class Kijis(models.Model):
    bunrui = models.ManyToManyField(Bunrui, related_name='bunrui', blank=True)
    category = models.ForeignKey(Category, blank=True, null=True, related_name='category', on_delete=models.SET_NULL)
    title = models.CharField(max_length=400, blank=True, null=True)
    author = models.ManyToManyField(Author, related_name='author', blank=True)
    volume = models.TextField(blank=True, null=True)
    startpage = models.SmallIntegerField(blank=True, null=True)
    no = models.TextField(blank=True, null=True)
    keyword = models.ManyToManyField(Keyword, related_name='keyword', blank=True)
    pdf = models.CharField(max_length=50, blank=True, null=True)



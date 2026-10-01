from django.db import models   

#Kijisのbunruiで参照（複数記事で同じものが出てくるため）
class Bunrui(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)

    # 管理画面で表示する日本語名称を定義する。
    class Meta:
        verbose_name = '内容分類'
        verbose_name_plural = '内容分類'

#Kijisのauthorで参照（複数記事で同じものが出てくるため）
class Author(models.Model):
    # 同名の著者を重複登録しない。
    name = models.CharField(max_length=256, unique=True)

    def __str__(self):
        return str(self.name)

    # 管理画面で表示する日本語名称を定義する。
    class Meta:
        verbose_name = '著者'
        verbose_name_plural = '著者'

#Kijisのkeywordで参照（複数記事で同じものが出てくるため）
class Keyword(models.Model):
    # 同名のキーワードを重複登録しない。
    name = models.CharField(max_length=256, unique=True)

    def __str__(self):
        return str(self.name)

    # 管理画面で表示する日本語名称を定義する。
    class Meta:
        verbose_name = 'キーワード'
        verbose_name_plural = 'キーワード'

# 詳細検索でカテゴリをまとめる原稿種別を管理する。
class CategoryGroup(models.Model):
    # 管理画面と詳細検索に表示する原稿種別名を保存する。
    name = models.CharField(max_length=100, unique=True)
    # 詳細検索と管理画面で使う原稿種別の表示順を保存する。
    display_order = models.PositiveSmallIntegerField(unique=True)

    def __str__(self):
        return str(self.name)

    # 原稿種別を表示順で扱うための管理情報を定義する。
    class Meta:
        ordering = ('display_order', 'id')
        verbose_name = '原稿種別'
        verbose_name_plural = '原稿種別'


# Kijisのcategoryで参照（複数記事で同じものが出てくるため）
class Category(models.Model):
    name = models.CharField(max_length=100)
    # カテゴリには、詳細検索で使う原稿種別を必ず所属させる。
    group = models.ForeignKey(
        CategoryGroup,
        blank=False,
        null=False,
        on_delete=models.PROTECT,
        related_name='categories',
    )

    def __str__(self):
        return str(self.name)

    # 管理画面で表示する日本語名称を定義する。
    class Meta:
        verbose_name = 'カテゴリ'
        verbose_name_plural = 'カテゴリ'

#記事のデータベース
class Kijis(models.Model):
    bunrui = models.ManyToManyField(Bunrui, related_name='bunrui', blank=True)
    # 使用中のカテゴリを削除して記事が未分類になることを防ぐ。
    category = models.ForeignKey(Category, blank=True, null=True, related_name='category', on_delete=models.PROTECT)
    title = models.CharField(max_length=400, blank=True, null=True)
    # 著者ごとの公開表示順をArticleAuthorで保持する。
    author = models.ManyToManyField(
        Author,
        related_name='author',
        through='ArticleAuthor',
        through_fields=('kijis', 'author'),
        blank=True,
    )
    volume = models.TextField(blank=True, null=True)
    startpage = models.SmallIntegerField(blank=True, null=True)
    no = models.TextField(blank=True, null=True)
    keyword = models.ManyToManyField(Keyword, related_name='keyword', blank=True)
    pdf = models.CharField(max_length=50, blank=True, null=True)

    # 管理画面と操作履歴で判別しやすい記事名を返す。
    def __str__(self):
        if self.title:
            return self.title
        if self.pk:
            return f'題名なしの記事 #{self.pk}'
        return '新規記事'

    # 管理画面で表示する日本語名称を定義する。
    class Meta:
        verbose_name = '記事'
        verbose_name_plural = '記事'


# 記事に紐付く著者と、公開時の表示順を管理する。
class ArticleAuthor(models.Model):
    # 記事を削除した場合は、対応する著者関連も削除する。
    kijis = models.ForeignKey(
        Kijis,
        on_delete=models.CASCADE,
        related_name='author_links',
    )
    # 使用中の著者名を誤って削除しないよう保護する。
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        related_name='article_author_links',
    )
    # 1から始まる公開時の著者表示順を記録する。0は旧処理との互換用。
    display_order = models.PositiveSmallIntegerField(default=0)

    # 管理画面と公開画面で同じ順序を使う。
    class Meta:
        db_table = 'list_kijis_author'
        ordering = ('display_order', 'id')
        verbose_name = '記事の著者'
        verbose_name_plural = '記事の著者'

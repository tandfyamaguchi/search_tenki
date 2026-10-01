from django.db import models


# 旧PHPシステムから引き継ぐ、読み取り専用の旧記事テーブルを表す。
class Kiji(models.Model):
    # フィールド定義はetenki.dbの既存スキーマに合わせ、migrationで管理しない。
    bunrui = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    title_jp = models.CharField(max_length=400, blank=True, null=True)
    author_jp = models.CharField(max_length=256, blank=True, null=True)
    # 旧DBとの互換性を優先し、巻・号は文字列として扱う。
    volume = models.TextField(blank=True, null=True)
    start_page = models.SmallIntegerField(blank=True, null=True)
    no = models.TextField(blank=True, null=True)
    keyword = models.CharField(max_length=256, blank=True, null=True)
    pdf = models.CharField(max_length=50, blank=True, null=True)

    # Djangoによるテーブル作成・変更を行わず、既存の旧DBテーブルを参照する。
    class Meta:
        managed = False
        db_table = 'kiji'


# 旧DBの内容分類テーブルを読み取り専用で参照する。
class Naiyou(models.Model):
    title = models.CharField(max_length=100)

    # Djangoのmigration対象外として、etenki.dbの既存テーブルをそのまま利用する。
    class Meta:
        managed = False
        db_table = 'naiyou'

    # 管理画面やエラー表示で内容分類名を返す。
    def __str__(self):
        return self.title

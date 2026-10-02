from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import TestCase

from list.models import Bunrui, Category, CategoryGroup, Kijis
from search.models import Month, Year

# 空の検索用DBへ初期投入して旧DB同期できることを確認する。
class InitializeSearchDbCommandTests(TestCase):
    databases = {'default', 'etenki'}

    # テスト用の旧DBに、unmanagedモデル用の表を作成する。
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connections['etenki'].cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS kiji (
                    id integer PRIMARY KEY,
                    bunrui varchar(100),
                    category varchar(100),
                    title_jp varchar(400),
                    author_jp varchar(256),
                    volume text,
                    start_page smallint,
                    no text,
                    keyword varchar(256),
                    pdf varchar(50)
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS naiyou (
                    id integer PRIMARY KEY,
                    title varchar(100) NOT NULL
                )
                '''
            )

    # 各テストで使う最小限の旧DBデータを用意する。
    def setUp(self):
        with connections['etenki'].cursor() as cursor:
            cursor.execute('DELETE FROM kiji')
            cursor.execute('DELETE FROM naiyou')
            cursor.executemany(
                'INSERT INTO naiyou (id, title) VALUES (?, ?)',
                [
                    (1, '気象一般'),
                    (501, '観測技術'),
                ],
            )
            cursor.executemany(
                '''
                INSERT INTO kiji (
                    id, bunrui, category, title_jp, author_jp,
                    volume, start_page, no, keyword, pdf
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    (
                        1001,
                        '1,501',
                        '1999年度 学位論文紹介',
                        '初回投入の記事',
                        '著者A・著者B ',
                        '10',
                        1,
                        '1',
                        '初期、同期、',
                        'initial.pdf',
                    ),
                    (
                        2003,
                        '',
                        '90年代の気象学への手引',
                        'カテゴリ確認の記事',
                        None,
                        '11',
                        2,
                        '2',
                        None,
                        None,
                    ),
                ],
            )

    # 初期投入がIDを維持し、同期済みの検索データを作る。
    def test_apply_seeds_and_synchronizes_an_empty_database(self):
        self.assertFalse(CategoryGroup.objects.exists())

        call_command('initialize_search_db', '--apply', stdout=StringIO())

        self.assertEqual(set(Kijis.objects.values_list('id', flat=True)), {1001, 2003})
        self.assertEqual(set(Bunrui.objects.values_list('id', flat=True)), {1, 501})
        self.assertEqual(Category.objects.count(), 206)
        self.assertEqual(CategoryGroup.objects.count(), 25)
        self.assertEqual(Year.objects.count(), 66)
        self.assertEqual(Month.objects.count(), 786)
        # CSVの巻・号対応を、同じ値にならないIDで確認する。
        second_issue = Month.objects.get(id=2)
        self.assertEqual(second_issue.volume_id, 1)
        self.assertEqual(second_issue.no, 2)
        self.assertEqual(second_issue.start_page, 33)

        article = Kijis.objects.get(id=1001)
        self.assertEqual(article.title, '初回投入の記事')
        self.assertEqual(article.category_id, 1)
        self.assertEqual(
            list(article.bunrui.values_list('id', flat=True)),
            [1, 501],
        )
        self.assertEqual(
            list(article.author_links.values_list('author__name', flat=True)),
            ['著者A', '著者B '],
        )
        self.assertEqual(
            set(article.keyword.values_list('name', flat=True)),
            {'初期', '同期', ''},
        )
        self.assertEqual(Category.objects.get(id=1).group.name, '学位論文紹介')
        self.assertEqual(Category.objects.get(id=2).group.name, 'その他')
        self.assertEqual(
            CategoryGroup.objects.get(name='学位論文紹介').display_order,
            14,
        )
        self.assertEqual(Year.objects.get(id=1).volume, 1)
        self.assertEqual(Month.objects.get(id=1).start_page, 1)

    # 検証モードが検索用DBを空のまま保持する。
    def test_dry_run_rolls_back_all_initial_data(self):
        self.assertFalse(CategoryGroup.objects.exists())

        call_command('initialize_search_db', '--dry-run', stdout=StringIO())

        self.assertFalse(Kijis.objects.exists())
        self.assertFalse(Bunrui.objects.exists())
        self.assertFalse(Category.objects.exists())
        self.assertFalse(Year.objects.exists())
        self.assertFalse(Month.objects.exists())
        self.assertFalse(CategoryGroup.objects.exists())

    # テスト用DBや既存DBを上書きしないことを確認する。
    def test_apply_rejects_a_nonempty_target_database(self):
        Kijis.objects.create(title='既存の記事')

        with self.assertRaisesMessage(CommandError, '既存データがあります'):
            call_command('initialize_search_db', '--apply', stdout=StringIO())

    # 原稿種別だけがあるDBも、初回投入対象として上書きしない。
    def test_apply_rejects_a_target_with_existing_category_groups(self):
        CategoryGroup.objects.create(name='既存の原稿種別', display_order=1)

        with self.assertRaisesMessage(CommandError, '既存データがあります'):
            call_command('initialize_search_db', '--apply', stdout=StringIO())

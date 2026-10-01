from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from search.models import Month, Year

from .models import ArticleAuthor, Author, Bunrui, Category, Kijis, Keyword
from .templatetags.mypaginator import sort_url


class DetailSearchInputValidationTests(TestCase):
    #パラメータなしで詳細検索結果URLを開いても200になる
    def test_direct_search_url_uses_safe_defaults(self):
        response = self.client.get(reverse('list:ShowList2'))
        self.assertEqual(response.status_code, 200)

    #pages=abc・0・100000 は400になり、エラーが表示される
    def test_invalid_page_size_returns_form_error(self):
        for value in ('abc', '0', '100000'):
            with self.subTest(value=value):
                response = self.client.get(
                    reverse('list:ShowList2'),
                    {'pages': value, 'order': '0'},
                )
                self.assertEqual(response.status_code, 400)
                self.assertContains(response, '正しく選択', status_code=400)

    #空白だけのタイトルを指定しても500エラーにならない
    def test_whitespace_only_term_does_not_crash(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {'title': '   ', 'pages': '10', 'order': '0'},
        )
        self.assertEqual(response.status_code, 200)

    # 不正な検索式を各入力欄のエラーとして返す。
    def test_invalid_search_syntax_returns_field_error(self):
        invalid_expressions = (
            'OR 台風',
            '台風 OR',
            '台風 OR OR 豪雨',
            '-',
            '--台風',
        )

        for field in ('title', 'author', 'word'):
            for expression in invalid_expressions:
                with self.subTest(field=field, expression=expression):
                    response = self.client.get(
                        reverse('list:ShowList2'),
                        {
                            field: expression,
                            'pages': '10',
                            'order': '0',
                        },
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.context['form'].errors)
                    self.assertContains(response, 'errorlist', status_code=400)

    # 検索式を含めても各入力欄の20文字上限を維持する。
    def test_search_expression_keeps_twenty_character_limit(self):
        for field in ('title', 'author', 'word'):
            with self.subTest(field=field):
                response = self.client.get(
                    reverse('list:ShowList2'),
                    {
                        field: 'あ' * 21,
                        'pages': '10',
                        'order': '0',
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.context['form'].errors)


# 巻・号の空欄が、検索条件なしとして扱われることを確認する。
class DetailSearchBlankVolumeIssueTests(TestCase):
    # 異なる巻・号の記事を用意する。
    @classmethod
    def setUpTestData(cls):
        cls.articles = [
            Kijis.objects.create(
                title='1件目の記事',
                volume='10',
                no='1',
                startpage=1,
            ),
            Kijis.objects.create(
                title='2件目の記事',
                volume='20',
                no='2',
                startpage=1,
            ),
        ]

    # 明示的に空欄を送信しても、巻・号では絞り込まない。
    def test_blank_volume_and_issue_return_all_articles(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {
                'vol': [''],
                'n': [''],
                'pages': '10',
                'order': '0',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(response.context['page_obj']),
            self.articles,
        )
        self.assertNotIn('巻:', response.context['joken'])
        self.assertNotIn('号:', response.context['joken'])


# 内容分類の選択値で、従来どおり記事を検索できることを確認する。
class DetailSearchBunruiTests(TestCase):
    # 異なる内容分類に属する記事を用意する。
    @classmethod
    def setUpTestData(cls):
        target_bunrui = Bunrui.objects.create(
            id=1041,
            name='総観規模の風',
        )
        other_bunrui = Bunrui.objects.create(id=2, name='大気物理化学')
        cls.target_article = Kijis.objects.create(
            title='検索対象の記事',
            volume='10',
            no='1',
            startpage=1,
        )
        other_article = Kijis.objects.create(
            title='対象外の記事',
            volume='10',
            no='1',
            startpage=2,
        )
        cls.target_article.bunrui.add(target_bunrui)
        other_article.bunrui.add(other_bunrui)

    # 送信した分類IDに一致する記事だけが返ることを確認する。
    def test_detail_search_filters_by_selected_bunrui_id(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {'bun': '1041', 'pages': '10', 'order': '0'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['page_obj']),
            [self.target_article],
        )
        self.assertContains(response, '内容分類:総観規模の風')


class DetailSearchOrderingTests(TestCase):
    # ID順と異なる巻・号・開始頁の記事を用意する。
    @classmethod
    def setUpTestData(cls):
        # ID順と、巻・号・開始頁の並び順が一致しない順番で作成する。
        Kijis.objects.create(volume='10', no='2', startpage=20)
        Kijis.objects.create(volume='2', no='10', startpage=99)
        Kijis.objects.create(volume='10', no='10', startpage=1)
        Kijis.objects.create(volume='10', no='2', startpage=5)

    # 詳細検索へ任意のGET条件を加え、巻・号・開始頁を返す。
    def search_result_values(self, order, **extra_params):
        params = {'pages': '10', 'order': order}
        params.update(extra_params)
        response = self.client.get(
            reverse('list:ShowList2'),
            params,
        )
        self.assertEqual(response.status_code, 200)
        return [
            (article.volume, article.no, article.startpage)
            for article in response.context['page_obj']
        ]

    # 詳細検索の昇順が、巻、号、開始頁の順になることを確認する。
    def test_articles_are_sorted_in_ascending_order(self):
        self.assertEqual(
            self.search_result_values('1'),
            [
                ('2', '10', 99),
                ('10', '2', 5),
                ('10', '2', 20),
                ('10', '10', 1),
            ],
        )

    # 詳細検索の降順が、巻、号、開始頁の順になることを確認する。
    def test_articles_are_sorted_in_descending_order(self):
        self.assertEqual(
            self.search_result_values('0'),
            [
                ('10', '10', 1),
                ('10', '2', 20),
                ('10', '2', 5),
                ('2', '10', 99),
            ],
        )

    # 数値見出しはどれを押しても、詳細検索と同じ複合順を使う。
    def test_numeric_headers_use_detail_search_composite_order(self):
        expected_by_direction = {
            'asc': self.search_result_values('1'),
            'desc': self.search_result_values('0'),
        }
        opposite_form_order = {'asc': '0', 'desc': '1'}

        for field in ('volume', 'no', 'startpage', 'publication'):
            for direction in ('asc', 'desc'):
                with self.subTest(field=field, direction=direction):
                    self.assertEqual(
                        self.search_result_values(
                            opposite_form_order[direction],
                            sort=field,
                            direction=direction,
                        ),
                        expected_by_direction[direction],
                    )


class DetailSearchIssueNumberTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        volume_2 = Year.objects.create(year=1955, volume=2)
        volume_4 = Year.objects.create(year=1957, volume=4)
        Month.objects.create(volume=volume_2, no=1, start_page=1)
        Month.objects.create(volume=volume_4, no=13, start_page=0)
        Kijis.objects.create(volume='2', no='1', startpage=1)
        cls.special_issue = Kijis.objects.create(
            volume='4',
            no='13',
            startpage=0,
        )

    def test_detail_search_can_find_issue_13(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {'n': ['13'], 'pages': '10', 'order': '0'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['page_obj']), [self.special_issue])
        self.assertContains(response, '号:13')


class DetailSearchExpressionTests(TestCase):
    # 検索演算子の確認に使う記事と関連データを用意する。
    @classmethod
    def setUpTestData(cls):
        cls.title_both = Kijis.objects.create(
            title='台風と豪雨の記録', volume='1', no='1', startpage=1
        )
        cls.title_typhoon = Kijis.objects.create(
            title='台風の記録', volume='1', no='1', startpage=2
        )
        cls.title_heavy_rain = Kijis.objects.create(
            title='豪雨の記録', volume='1', no='1', startpage=3
        )
        cls.title_excluded = Kijis.objects.create(
            title='台風速報', volume='1', no='1', startpage=4
        )

        author_a = Author.objects.create(name='丸山')
        author_b = Author.objects.create(name='浜田')
        author_excluded = Author.objects.create(name='佐藤')
        cls.author_both = Kijis.objects.create(
            title='著者両方', volume='2', no='1', startpage=1
        )
        cls.author_only_a = Kijis.objects.create(
            title='著者丸山', volume='2', no='1', startpage=2
        )
        cls.author_only_b = Kijis.objects.create(
            title='著者浜田', volume='2', no='1', startpage=3
        )
        cls.author_with_excluded = Kijis.objects.create(
            title='著者除外対象', volume='2', no='1', startpage=4
        )
        cls.author_both.author.add(author_a, author_b)
        cls.author_only_a.author.add(author_a)
        cls.author_only_b.author.add(author_b)
        cls.author_with_excluded.author.add(author_a, author_excluded)

        keyword_a = Keyword.objects.create(name='大雨')
        keyword_b = Keyword.objects.create(name='豪雨')
        keyword_excluded = Keyword.objects.create(name='速報')
        cls.keyword_both = Kijis.objects.create(
            title='用語両方', volume='3', no='1', startpage=1
        )
        cls.keyword_only_a = Kijis.objects.create(
            title='用語一', volume='3', no='1', startpage=2
        )
        cls.keyword_only_b = Kijis.objects.create(
            title='用語二', volume='3', no='1', startpage=3
        )
        cls.keyword_with_excluded = Kijis.objects.create(
            title='キーワード除外対象', volume='3', no='1', startpage=4
        )
        cls.keyword_both.keyword.add(keyword_a, keyword_b)
        cls.keyword_only_a.keyword.add(keyword_a)
        cls.keyword_only_b.keyword.add(keyword_b)
        cls.keyword_with_excluded.keyword.add(
            keyword_a,
            keyword_excluded,
        )

    # 詳細検索を実行して応答を返す。
    def search_response(self, **conditions):
        conditions.update({'pages': '100', 'order': '0'})
        response = self.client.get(reverse('list:ShowList2'), conditions)
        self.assertEqual(response.status_code, 200)
        return response

    # 空白区切りのタイトル語がすべて必要になることを確認する。
    def test_space_separated_title_terms_use_and_search(self):
        response = self.search_response(title='台風 豪雨')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.title_both],
        )

    # タイトル欄の独立したORがいずれかの語に一致することを確認する。
    def test_title_or_search_matches_any_term(self):
        response = self.search_response(title='台風 OR 豪雨')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [
                self.title_both,
                self.title_typhoon,
                self.title_heavy_rain,
                self.title_excluded,
            ],
        )

    # タイトル欄では空白ANDを優先してからOR候補をまとめる。
    def test_title_and_or_search_uses_grouped_terms(self):
        response = self.search_response(title='台風 豪雨 OR 速報')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.title_both, self.title_excluded],
        )

    # タイトル欄のハイフン語が一致記事を除外することを確認する。
    def test_title_not_search_excludes_term(self):
        response = self.search_response(title='台風 -速報')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.title_both, self.title_typhoon],
        )

    # タイトル欄ではOR候補すべてにNOTが適用されることを確認する。
    def test_title_or_and_not_uses_global_exclusion(self):
        response = self.search_response(title='台風 OR 豪雨 -速報')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [
                self.title_both,
                self.title_typhoon,
                self.title_heavy_rain,
            ],
        )

    # 著者の空白ANDが別々の関連レコードにも一致することを確認する。
    def test_author_and_search_matches_separate_related_records(self):
        response = self.search_response(author='丸山 浜田')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.author_both],
        )

    # キーワードの空白ANDが別々の関連レコードにも一致することを確認する。
    def test_keyword_and_search_matches_separate_related_records(self):
        response = self.search_response(word='大雨 豪雨')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.keyword_both],
        )

    # 著者のOR検索で同じ記事が重複しないことを確認する。
    def test_author_or_search_returns_each_article_once(self):
        response = self.search_response(author='丸山 OR 浜田')
        articles = list(response.context['page_obj'])

        self.assertCountEqual(
            articles,
            [
                self.author_both,
                self.author_only_a,
                self.author_only_b,
                self.author_with_excluded,
            ],
        )
        self.assertEqual(len(articles), len({article.id for article in articles}))
        self.assertEqual(response.context['kensu'], 4)
        self.assertEqual(response.context['page_obj'].paginator.count, 4)

    # キーワードのOR検索で同じ記事が重複しないことを確認する。
    def test_keyword_or_search_returns_each_article_once(self):
        response = self.search_response(word='大雨 OR 豪雨')
        articles = list(response.context['page_obj'])

        self.assertCountEqual(
            articles,
            [
                self.keyword_both,
                self.keyword_only_a,
                self.keyword_only_b,
                self.keyword_with_excluded,
            ],
        )
        self.assertEqual(len(articles), len({article.id for article in articles}))
        self.assertEqual(response.context['kensu'], 4)
        self.assertEqual(response.context['page_obj'].paginator.count, 4)

    # 著者欄ではOR候補すべてにNOTが適用されることを確認する。
    def test_author_or_and_not_uses_global_exclusion(self):
        response = self.search_response(author='丸山 OR 浜田 -佐藤')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.author_both, self.author_only_a, self.author_only_b],
        )

    # キーワード欄ではOR候補すべてにNOTが適用されることを確認する。
    def test_keyword_or_and_not_uses_global_exclusion(self):
        response = self.search_response(word='大雨 OR 豪雨 -速報')

        self.assertCountEqual(
            list(response.context['page_obj']),
            [self.keyword_both, self.keyword_only_a, self.keyword_only_b],
        )


class ArticleListQueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='解説')
        cls.classification = Bunrui.objects.create(name='気候')
        author = Author.objects.create(name='テスト著者')
        keyword = Keyword.objects.create(name='テスト用語')
        year = Year.objects.create(year=1963, volume=10)
        cls.issue = Month.objects.create(volume=year, no=1, start_page=1)

        for number in range(30):
            article = Kijis.objects.create(
                category=category,
                title=f'記事{number}',
                volume='10',
                no='1',
                startpage=number + 1,
            )
            article.bunrui.add(cls.classification)
            article.author.add(author)
            article.keyword.add(keyword)

    # 一覧表示のクエリ数が記事数に比例して増えないことを確認する。
    def assert_list_uses_few_queries(self, url, params=None):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, params or {})
            response.content

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 30)
        self.assertEqual(response.context['kensu'], 30)
        self.assertEqual(response.context['page_obj'].paginator.count, 30)
        for related_name in ('解説', '気候', 'テスト著者', 'テスト用語'):
            self.assertContains(response, related_name)
        self.assertLessEqual(len(queries), 8)

    def test_issue_list_avoids_queries_for_each_article(self):
        self.assert_list_uses_few_queries(
            reverse('list:ShowList1', kwargs={'id': self.issue.id})
        )

    def test_detail_search_avoids_queries_for_each_article(self):
        self.assert_list_uses_few_queries(
            reverse('list:ShowList2'),
            {'pages': '30', 'order': '0'},
        )

    def test_related_item_list_avoids_queries_for_each_article(self):
        self.assert_list_uses_few_queries(
            reverse(
                'list:ShowList3',
                kwargs={'id': self.classification.id, 'shurui': 0},
            )
        )


# 文字列列が簡易の自然順と空欄規則で並ぶことを確認する。
class ArticleTextHeaderSortingTests(TestCase):
    # 文字種と空欄を含む記事を、意図した順とは異なるID順で用意する。
    @classmethod
    def setUpTestData(cls):
        values = [
            ('あ2', 'あ2', 'あ2'),
            ('あ10', 'あ10', 'あ10'),
            ('Ａlpha', 'Ａlpha', 'Beta'),
            ('beta', 'beta', 'alpha'),
            ('2番', '2分類', '2著者'),
            ('10番', '10分類', '10著者'),
            ('éclair', 'é分類', 'é著者'),
            (None, None, None),
            ('  ', '  ', '  '),
        ]
        cls.articles = []
        for title, category_name, author_name in values:
            category = None
            if category_name is not None:
                category = Category.objects.create(name=category_name)
            article = Kijis.objects.create(
                category=category,
                title=title,
                volume='1',
                no='1',
                startpage=1,
            )
            if author_name is not None:
                article.author.add(Author.objects.create(name=author_name))
            cls.articles.append(article)

        # 3件目は2人目が日本語でも、登録順の先頭著者「Beta」で比較する。
        cls.second_author = Author.objects.create(name='ああ')
        cls.articles[2].author.add(cls.second_author)

    # 詳細検索結果を指定列で並べ、記事IDの順を返す。
    def sorted_article_ids(self, field, direction='asc'):
        response = self.client.get(
            reverse('list:ShowList2'),
            {
                'pages': '100',
                'order': '0',
                'sort': field,
                'direction': direction,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response, [
            article.id for article in response.context['page_obj']
        ]

    # タイトルを日本語、英字、数字、その他、空欄の自然順で並べる。
    def test_title_sort_uses_simple_natural_order(self):
        _, article_ids = self.sorted_article_ids('title')
        expected_indexes = [0, 1, 2, 3, 4, 5, 6, 8, 7]
        self.assertEqual(
            article_ids,
            [self.articles[index].id for index in expected_indexes],
        )

    # カテゴリーもタイトルと同じ文字種の規則で並べる。
    def test_category_sort_uses_simple_natural_order(self):
        _, article_ids = self.sorted_article_ids('category')
        expected_indexes = [0, 1, 2, 3, 4, 5, 6, 8, 7]
        self.assertEqual(
            article_ids,
            [self.articles[index].id for index in expected_indexes],
        )

    # 著者は中間テーブルの登録順における先頭著者で並べる。
    def test_author_sort_uses_first_registered_author(self):
        response, article_ids = self.sorted_article_ids('author')
        expected_indexes = [0, 1, 3, 2, 4, 5, 6, 8, 7]
        self.assertEqual(
            article_ids,
            [self.articles[index].id for index in expected_indexes],
        )

        third_article = next(
            article
            for article in response.context['page_obj']
            if article.id == self.articles[2].id
        )
        self.assertEqual(
            [author.name for author in third_article.ordered_authors],
            ['Beta', 'ああ'],
        )

    # 降順ではNULLと空文字相当の記事を先頭へ移動する。
    def test_descending_text_sort_puts_blanks_first(self):
        _, article_ids = self.sorted_article_ids('title', 'desc')
        self.assertEqual(
            article_ids[:2],
            [self.articles[7].id, self.articles[8].id],
        )
        self.assertEqual(
            article_ids[2:],
            [
                self.articles[index].id
                for index in [6, 5, 4, 3, 2, 1, 0]
            ],
        )


# 数値列が文字列順ではなく数値順で並ぶことを確認する。
class ArticleNumericHeaderSortingTests(TestCase):
    # NULL、空文字、2、10を含む記事を用意する。
    @classmethod
    def setUpTestData(cls):
        cls.blank_none = Kijis.objects.create(
            title='NULL', volume=None, no=None, startpage=None
        )
        cls.blank_text = Kijis.objects.create(
            title='空文字', volume='', no='', startpage=None
        )
        cls.two = Kijis.objects.create(
            title='2', volume='2', no='2', startpage=2
        )
        cls.ten = Kijis.objects.create(
            title='10', volume='10', no='10', startpage=10
        )

    # 指定した数値列で詳細検索結果を並べ、記事IDの順を返す。
    def sorted_article_ids(self, field, direction):
        response = self.client.get(
            reverse('list:ShowList2'),
            {
                'pages': '100',
                'order': '0',
                'sort': field,
                'direction': direction,
            },
        )
        self.assertEqual(response.status_code, 200)
        return [article.id for article in response.context['page_obj']]

    # 巻と号は数値順になり、空欄の位置は昇降順で入れ替わる。
    def test_volume_and_issue_sort_numerically_with_directional_blanks(self):
        for field in ('volume', 'no'):
            with self.subTest(field=field, direction='asc'):
                article_ids = self.sorted_article_ids(field, 'asc')
                self.assertEqual(article_ids[:2], [self.two.id, self.ten.id])
                self.assertCountEqual(
                    article_ids[2:],
                    [self.blank_none.id, self.blank_text.id],
                )
            with self.subTest(field=field, direction='desc'):
                article_ids = self.sorted_article_ids(field, 'desc')
                self.assertCountEqual(
                    article_ids[:2],
                    [self.blank_none.id, self.blank_text.id],
                )
                self.assertEqual(
                    article_ids[2:],
                    [self.ten.id, self.two.id],
                )

    # 開始頁も数値順になり、NULLは昇順で末尾、降順で先頭になる。
    def test_start_page_sort_uses_numeric_direction(self):
        ascending = self.sorted_article_ids('startpage', 'asc')
        self.assertEqual(ascending[:2], [self.two.id, self.ten.id])
        self.assertCountEqual(
            ascending[2:],
            [self.blank_none.id, self.blank_text.id],
        )

        descending = self.sorted_article_ids('startpage', 'desc')
        self.assertCountEqual(
            descending[:2],
            [self.blank_none.id, self.blank_text.id],
        )
        self.assertEqual(
            descending[2:],
            [self.ten.id, self.two.id],
        )


# 3種類の記事一覧すべてで見出し並び替えが有効なことを確認する。
class ArticleSortingViewCoverageTests(TestCase):
    # 巻号一覧と関連項目一覧の両方に現れる記事を用意する。
    @classmethod
    def setUpTestData(cls):
        year = Year.objects.create(year=1963, volume=10)
        cls.issue = Month.objects.create(volume=year, no=1, start_page=1)
        cls.classification = Bunrui.objects.create(name='確認用分類')
        cls.later = Kijis.objects.create(
            title='い', volume='10', no='1', startpage=20
        )
        cls.earlier = Kijis.objects.create(
            title='あ', volume='10', no='1', startpage=2
        )
        cls.later.bunrui.add(cls.classification)
        cls.earlier.bunrui.add(cls.classification)

    # 巻号から開く一覧で開始頁の昇順を使える。
    def test_issue_list_accepts_header_sort(self):
        response = self.client.get(
            reverse('list:ShowList1', kwargs={'id': self.issue.id}),
            {'sort': 'startpage', 'direction': 'asc'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['page_obj']),
            [self.earlier, self.later],
        )
        self.assertEqual(response.context['sort_field'], 'publication')

    # 年度（巻）検索の初期結果を、刊行順の降順で表示する。
    def test_issue_list_defaults_to_descending_publication_order(self):
        response = self.client.get(
            reverse('list:ShowList1', kwargs={'id': self.issue.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['page_obj']),
            [self.later, self.earlier],
        )
        self.assertEqual(response.context['sort_field'], 'publication')
        self.assertEqual(response.context['sort_direction'], 'desc')

    # 関連項目から開く一覧でタイトルの昇順を使える。
    def test_related_item_list_accepts_header_sort(self):
        response = self.client.get(
            reverse(
                'list:ShowList3',
                kwargs={'id': self.classification.id, 'shurui': 0},
            ),
            {'sort': 'title', 'direction': 'asc'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['page_obj']),
            [self.earlier, self.later],
        )


# 見出しリンクと上下の見出し表示を確認する。
class ArticleSortingHeaderTemplateTests(TestCase):
    # 表示確認に使う記事を1件作成する。
    @classmethod
    def setUpTestData(cls):
        Kijis.objects.create(
            title='表示確認', volume='1', no='1', startpage=1
        )

    # 上下の見出しと、検索結果の交互のグレー背景を表示する。
    def test_top_and_bottom_headers_are_styled_and_clickable(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {
                'pages': '10',
                'order': '0',
                'sort': 'title',
                'direction': 'asc',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<tfoot>')
        self.assertContains(response, 'background-color: #edf7d0;')
        self.assertContains(response, 'tbody tr:nth-child(odd)')
        self.assertContains(response, 'background-color: #f0f0f0;')
        self.assertContains(response, 'tbody tr:nth-child(even)')
        self.assertContains(response, 'background-color: #fafafa;')
        self.assertContains(response, 'sort=title', count=2)
        self.assertContains(response, 'direction=desc', count=2)
        self.assertContains(response, 'aria-sort="ascending"', count=1)
        self.assertContains(
            response,
            '<span aria-hidden="true">▼▲</span>',
            count=10,
        )
        self.assertContains(
            response,
            '<span aria-hidden="true">▲</span>',
            count=2,
        )

    # 刊行順では数値3列が同じ矢印とリンク先を表示する。
    def test_publication_headers_share_sort_state(self):
        descending = self.client.get(
            reverse('list:ShowList2'),
            {'pages': '10', 'order': '0'},
        )
        self.assertEqual(descending.status_code, 200)
        self.assertContains(descending, 'sort=publication', count=6)
        self.assertContains(
            descending,
            '<span aria-hidden="true">▼</span>',
            count=6,
        )
        self.assertContains(
            descending,
            '<span aria-hidden="true">▼▲</span>',
            count=6,
        )
        self.assertContains(
            descending,
            'aria-sort="descending"',
            count=1,
        )

        ascending = self.client.get(
            reverse('list:ShowList2'),
            {'pages': '10', 'order': '1'},
        )
        self.assertEqual(ascending.status_code, 200)
        self.assertContains(ascending, 'direction=desc', count=6)
        self.assertContains(
            ascending,
            '<span aria-hidden="true">▲</span>',
            count=6,
        )
        self.assertContains(ascending, 'aria-sort="ascending"', count=1)

    # 並び替えURLは複数選択を保ち、同じ列を押すと向きを反転する。
    def test_sort_url_preserves_filters_and_resets_page(self):
        request = RequestFactory().get(
            '/list/list2/?categ=1&categ=2&page=3&sort=title&direction=asc'
        )
        query = parse_qs(sort_url(request, 'title', 'title', 'asc'))

        self.assertEqual(query['categ'], ['1', '2'])
        self.assertEqual(query['sort'], ['title'])
        self.assertEqual(query['direction'], ['desc'])
        self.assertNotIn('page', query)

    # 許可していない列名は無視し、詳細検索の刊行順を使う。
    def test_invalid_sort_field_is_ignored(self):
        response = self.client.get(
            reverse('list:ShowList2'),
            {
                'pages': '10',
                'order': '0',
                'sort': 'not_a_column',
                'direction': 'asc',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sort_field'], 'publication')
        self.assertEqual(response.context['sort_direction'], 'desc')


# 記事を主運用するadminの追加・著者・破棄操作を確認する。
class ArticleAdminTests(TestCase):
    # 記事入力に必要な発行管理と関連データを用意する。
    @classmethod
    def setUpTestData(cls):
        cls.year = Year.objects.create(year=2019, volume=66)
        cls.issue_one = Month.objects.create(
            volume=cls.year,
            no=1,
            start_page=3,
        )
        cls.issue_two = Month.objects.create(
            volume=cls.year,
            no=2,
            start_page=113,
        )
        cls.category = Category.objects.create(name='解説')
        cls.bunrui = Bunrui.objects.create(name='気候')
        cls.first_author = Author.objects.create(name='著者A')
        cls.keyword = Keyword.objects.create(name='気候変動')
        cls.admin_user = get_user_model().objects.create_superuser(
            username='article-admin',
            email='article-admin@example.invalid',
            password='test-password',
        )

    # 各テストを全権限の管理者として実行する。
    def setUp(self):
        self.client.force_login(self.admin_user)

    # 記事追加フォームへ送信する共通データを作る。
    def article_form_data(self, **overrides):
        data = {
            'title': '管理画面から追加した記事',
            'volume': str(self.year.volume),
            'no': str(self.issue_one.no),
            'startpage': '3',
            'pdf': '2026/example.pdf',
            'category': str(self.category.pk),
            'bunrui': [str(self.bunrui.pk)],
            'keyword': [str(self.keyword.pk)],
            'author_links-TOTAL_FORMS': '1',
            'author_links-INITIAL_FORMS': '0',
            'author_links-MIN_NUM_FORMS': '0',
            'author_links-MAX_NUM_FORMS': '1000',
            'author_links-0-display_order': '1',
            'author_links-0-author': str(self.first_author.pk),
        }
        data.update(overrides)
        return data

    # 既存記事を変更・削除テスト用に作成する。
    def create_article_with_author(self):
        article = Kijis.objects.create(
            title='既存記事',
            volume=str(self.year.volume),
            no=str(self.issue_one.no),
            startpage=3,
            category=self.category,
        )
        article.bunrui.add(self.bunrui)
        article.keyword.add(self.keyword)
        relation = ArticleAuthor.objects.create(
            kijis=article,
            author=self.first_author,
            display_order=1,
        )
        return article, relation

    # 記事追加画面には巻・号選択と、未保存入力を破棄する導線を表示する。
    def test_add_form_shows_publication_author_and_discard_controls(self):
        response = self.client.get(reverse('admin:list_kijis_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_volume"')
        self.assertContains(response, 'id="id_no"')
        self.assertContains(response, '著者（公開表示順）')
        self.assertContains(response, 'id="id_author_links-0-author"')
        self.assertContains(response, '入力を破棄して記事一覧へ戻る', count=2)
        self.assertContains(response, 'data-discard-article', count=2)
        self.assertContains(response, 'list/js/article_admin.js')

    # 号の操作リンクから渡す巻・号を初期値として表示できる。
    def test_add_form_accepts_initial_publication_from_query_parameters(self):
        response = self.client.get(
            reverse('admin:list_kijis_add'),
            {'volume': self.year.volume, 'no': self.issue_two.no},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context['adminform'].form
        self.assertEqual(form['volume'].value(), str(self.year.volume))
        self.assertEqual(form['no'].value(), str(self.issue_two.no))

    # 記事追加時に指定した著者表示順を公開画面でも使う。
    def test_add_article_saves_and_publishes_specified_author_order(self):
        second_author = Author.objects.create(name='著者B')
        data = self.article_form_data(
            **{
                'author_links-TOTAL_FORMS': '2',
                'author_links-0-display_order': '2',
                'author_links-0-author': str(self.first_author.pk),
                'author_links-1-display_order': '1',
                'author_links-1-author': str(second_author.pk),
            }
        )

        response = self.client.post(reverse('admin:list_kijis_add'), data)

        self.assertEqual(response.status_code, 302)
        saved_article = Kijis.objects.get(title='管理画面から追加した記事')
        self.assertEqual(
            list(
                ArticleAuthor.objects.filter(kijis=saved_article).values_list(
                    'author__name',
                    'display_order',
                )
            ),
            [('著者B', 1), ('著者A', 2)],
        )

        public_response = self.client.get(
            reverse('list:ShowList1', kwargs={'id': self.issue_one.pk})
        )
        self.assertEqual(public_response.status_code, 200)
        public_article = next(
            listed_article
            for listed_article in public_response.context['page_obj']
            if listed_article.pk == saved_article.pk
        )
        self.assertEqual(
            [author.name for author in public_article.ordered_authors],
            ['著者B', '著者A'],
        )

    # 同じ著者や同じ表示順を複数行に登録できない。
    def test_add_article_rejects_duplicate_author_and_display_order(self):
        second_author = Author.objects.create(name='重複確認用著者')
        data = self.article_form_data(
            **{
                'author_links-TOTAL_FORMS': '2',
                'author_links-1-display_order': '1',
                'author_links-1-author': str(second_author.pk),
            }
        )

        response = self.client.post(reverse('admin:list_kijis_add'), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '同じ表示順は指定できません。')
        self.assertFalse(Kijis.objects.filter(title='管理画面から追加した記事').exists())

    # 著者行の削除は、著者名ではなく記事との関連だけを外す。
    def test_change_form_can_unlink_an_author_without_deleting_name(self):
        article, relation = self.create_article_with_author()
        data = self.article_form_data(
            **{
                'title': article.title,
                'volume': article.volume,
                'no': article.no,
                'startpage': str(article.startpage),
                'pdf': '',
                'author_links-TOTAL_FORMS': '1',
                'author_links-INITIAL_FORMS': '1',
                'author_links-0-id': str(relation.pk),
                'author_links-0-display_order': '1',
                'author_links-0-author': str(self.first_author.pk),
                'author_links-0-DELETE': 'on',
                '_save': '保存',
            }
        )

        response = self.client.post(
            reverse('admin:list_kijis_change', args=(article.pk,)),
            data,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ArticleAuthor.objects.filter(pk=relation.pk).exists())
        self.assertTrue(Author.objects.filter(pk=self.first_author.pk).exists())

    # 未使用の著者だけを削除でき、使用中の著者は削除画面にも進めない。
    def test_author_deletion_is_limited_to_unused_names(self):
        article, _relation = self.create_article_with_author()
        unused_author = Author.objects.create(name='未使用の著者')

        used_delete_url = reverse('admin:list_author_delete', args=(self.first_author.pk,))
        unused_delete_url = reverse('admin:list_author_delete', args=(unused_author.pk,))
        changelist_response = self.client.get(
            reverse('admin:list_author_changelist')
        )
        self.assertContains(changelist_response, '使用中の記事数')
        self.assertContains(changelist_response, '使用中')
        self.assertContains(changelist_response, unused_delete_url)
        self.assertEqual(self.client.get(used_delete_url).status_code, 403)
        self.assertEqual(self.client.get(unused_delete_url).status_code, 200)

        response = self.client.post(unused_delete_url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Kijis.objects.filter(pk=article.pk).exists())
        self.assertTrue(Author.objects.filter(pk=self.first_author.pk).exists())
        self.assertFalse(Author.objects.filter(pk=unused_author.pk).exists())

    # 著者一覧では、未使用の著者だけに削除操作を表示する。
    def test_author_changelist_shows_delete_link_only_for_unused_names(self):
        self.create_article_with_author()
        unused_author = Author.objects.create(name='未使用の著者')

        response = self.client.get(reverse('admin:list_author_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('admin:list_author_delete', args=(unused_author.pk,)),
        )
        self.assertNotContains(
            response,
            reverse('admin:list_author_delete', args=(self.first_author.pk,)),
        )
        self.assertContains(response, '使用中')

    # 破棄リンクは新規追加画面だけに表示し、既存記事の編集画面には出さない。
    def test_discard_link_is_only_shown_while_adding_article(self):
        article, _relation = self.create_article_with_author()

        add_response = self.client.get(reverse('admin:list_kijis_add'))
        change_response = self.client.get(
            reverse('admin:list_kijis_change', args=(article.pk,))
        )

        self.assertContains(add_response, '入力を破棄して記事一覧へ戻る')
        self.assertNotContains(change_response, '入力を破棄して記事一覧へ戻る')

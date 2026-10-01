from django import forms
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from list.models import Bunrui, Category, CategoryGroup, Kijis

from .forms import SearchDetailForm
from .models import Month, Year


# 内容分類の番号付き表示と階層順を確認する。
class SearchDetailBunruiChoiceTests(TestCase):
    # 内容分類を、画面の表示順とは異なる順番で登録する。
    @classmethod
    def setUpTestData(cls):
        bunrui_data = (
            (999999, '独自分類'),
            (16, '固体地球'),
            (10, '地球関連分野'),
            (9, '気象学関連雑記'),
            (5012, 'レーダー'),
            (50111, 'ゾンデ'),
            (5011, '一般測器'),
            (501, '観測技術'),
            (5, '研究技術'),
            (2021, '氷の物性'),
            (202, '雲物理'),
            (2, '大気物理化学'),
            (110, '惑星気象'),
            (1093, '局地風（地形風）'),
            (10921, '海陸風'),
            (1092, '局地循環（熱的原因による）'),
            (105, '中小規模大気擾乱'),
            (1042, '総観規模の降水'),
            (1041, '総観規模の風'),
            (104, '総観気象（時系列を含む）'),
            (101, '気象力学（熱学、地球流体力学を含む）'),
            (1, '気象一般'),
        )
        for bunrui_id, name in bunrui_data:
            Bunrui.objects.create(id=bunrui_id, name=name)

    # 内容分類が、親の直後に子が続く階層順になることを確認する。
    def test_bunrui_choices_use_reference_hierarchy_order(self):
        form = SearchDetailForm()
        choices = list(form.fields['bun'].choices)[1:]
        values = [int(str(value)) for value, _label in choices]

        self.assertEqual(
            values,
            [
                1, 101, 104, 1041, 1042, 105, 1092, 10921, 1093, 110,
                2, 202, 2021, 5, 501, 5011, 50111, 5012, 9, 10, 16,
                999999,
            ],
        )

    # 内容分類に、階層記号・分類番号・名称が表示されることを確認する。
    def test_bunrui_choices_show_numbered_tree_labels(self):
        form = SearchDetailForm()
        choices = list(form.fields['bun'].choices)[1:]
        labels = {
            int(str(value)): str(label) for value, label in choices
        }

        self.assertEqual(labels[1], '1. 気象一般')
        self.assertEqual(
            labels[101],
            '├101. 気象力学（熱学、地球流体力学を含む）',
        )
        self.assertEqual(labels[1041], '│├1041. 総観規模の風')
        self.assertEqual(labels[1042], '│└1042. 総観規模の降水')
        self.assertEqual(labels[10921], '││└10921. 海陸風')
        self.assertEqual(labels[110], '└110. 惑星気象')
        self.assertEqual(labels[50111], '││└50111. ゾンデ')
        self.assertEqual(labels[999999], '999999. 独自分類')

    # 選択した分類番号が、従来どおりBunruiとして検証されることを確認する。
    def test_selected_bunrui_is_cleaned_as_model_instance(self):
        form = SearchDetailForm({'bun': '1041'})

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(form.cleaned_data['bun'], Bunrui.objects.get(id=1041))


# 巻・号の選択肢と、空欄を選んだ場合の動作を確認する。
class SearchDetailIssueChoiceTests(TestCase):
    # 複数の巻と、重複する号を含むテストデータを用意する。
    @classmethod
    def setUpTestData(cls):
        volume_2 = Year.objects.create(year=1955, volume=2)
        volume_4 = Year.objects.create(year=1957, volume=4)
        Month.objects.create(volume=volume_2, no=1, start_page=1)
        Month.objects.create(volume=volume_2, no=2, start_page=1)
        Month.objects.create(volume=volume_4, no=1, start_page=1)
        Month.objects.create(volume=volume_4, no=13, start_page=0)

    # 空の候補を出さず、重複のない号を表示する。
    def test_issue_choices_use_distinct_numbers_from_all_volumes(self):
        form = SearchDetailForm()
        values = [value for value, _label in form.fields['n'].choices]
        self.assertEqual(values, [1, 2, 13])

    # 巻と号は、未チェックの状態だけで未選択にできることを確認する。
    def test_volume_and_issue_choices_do_not_show_blank_choice(self):
        form = SearchDetailForm()
        volume_values = [str(value) for value, _label in form.fields['vol'].choices]
        issue_values = [str(value) for value, _label in form.fields['n'].choices]

        self.assertNotIn('', volume_values)
        self.assertNotIn('', issue_values)

    # 空欄が送信された場合は、巻と号を未選択として扱う。
    def test_blank_choice_clears_volume_and_issue(self):
        form = SearchDetailForm(
            {
                'vol': [''],
                'n': [''],
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(list(form.cleaned_data['vol']), [])
        self.assertEqual(form.cleaned_data['n'], [])

    # 空欄と通常値が同時に送られた場合は、通常値を選択として残す。
    def test_blank_choice_does_not_discard_selected_values(self):
        form = SearchDetailForm(
            {
                'vol': ['', '2'],
                'n': ['', '13'],
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(
            [year.volume for year in form.cleaned_data['vol']],
            [2],
        )
        self.assertEqual(form.cleaned_data['n'], [13])

    # 空欄と不正な値が同時に送られても、不正値を検証エラーにする。
    def test_blank_choice_does_not_hide_invalid_values(self):
        form = SearchDetailForm(
            {
                'vol': ['', '999'],
                'n': ['', '999'],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('vol', form.errors)
        self.assertIn('n', form.errors)

    # 通常の巻を選んだ場合は、従来どおりYearとして検証する。
    def test_selected_volume_is_cleaned_as_model_queryset(self):
        form = SearchDetailForm({'vol': ['2']})

        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(
            [year.volume for year in form.cleaned_data['vol']],
            [2],
        )

    # 通常の号を選んだ場合は、従来どおり整数に変換する。
    def test_issue_number_is_cleaned_as_integer(self):
        form = SearchDetailForm({'n': ['13']})
        self.assertTrue(form.is_valid(), form.errors.as_text())
        self.assertEqual(form.cleaned_data['n'], [13])


# カテゴリ選択欄の表示形式とID順を確認する。
class SearchDetailCategoryChoiceTests(TestCase):
    # ID順と記事数順が異なるカテゴリを用意する。
    @classmethod
    def setUpTestData(cls):
        cls.group = CategoryGroup.objects.create(
            name='カテゴリ順テスト用原稿種別',
            display_order=90,
        )
        cls.unused = Category.objects.create(
            name='未使用カテゴリ',
            group=cls.group,
        )
        cls.most_used = Category.objects.create(
            name='最多カテゴリ',
            group=cls.group,
        )
        cls.second_same_count = Category.objects.create(
            name='Beta',
            group=cls.group,
        )
        cls.first_same_count = Category.objects.create(
            name='Alpha',
            group=cls.group,
        )

        for index in range(3):
            Kijis.objects.create(
                category=cls.most_used,
                title=f'最多カテゴリの記事{index}',
            )
        for index in range(2):
            Kijis.objects.create(
                category=cls.first_same_count,
                title=f'Alphaの記事{index}',
            )
            Kijis.objects.create(
                category=cls.second_same_count,
                title=f'Betaの記事{index}',
            )

    # カテゴリ欄が、複数選択用のチェックボックスであることを確認する。
    def test_category_field_uses_checkbox_select_multiple(self):
        form = SearchDetailForm()

        self.assertIsInstance(
            form.fields['categ'],
            forms.ModelMultipleChoiceField,
        )
        self.assertIsInstance(
            form.fields['categ'].widget,
            forms.CheckboxSelectMultiple,
        )

    # カテゴリを登録IDの昇順で表示することを確認する。
    def test_category_choices_are_ordered_by_id(self):
        form = SearchDetailForm()
        categories = list(form.fields['categ'].queryset)

        self.assertEqual(
            [category.id for category in categories],
            [
                self.unused.id,
                self.most_used.id,
                self.second_same_count.id,
                self.first_same_count.id,
            ],
        )


# カテゴリの原稿種別と表示順を、DBの管理値から取得することを確認する。
class SearchDetailCategoryGroupDatabaseTests(TestCase):
    # 初期移行済みの原稿種別より後ろに、テスト用の原稿種別を追加する。
    @classmethod
    def setUpTestData(cls):
        cls.first_group = CategoryGroup.objects.create(
            name='テスト原稿種別A',
            display_order=90,
        )
        cls.second_group = CategoryGroup.objects.create(
            name='テスト原稿種別B',
            display_order=91,
        )
        cls.first_category = Category.objects.create(
            name='テストカテゴリA',
            group=cls.first_group,
        )
        cls.second_category = Category.objects.create(
            name='テストカテゴリB',
            group=cls.second_group,
        )

    # 詳細検索のカテゴリ表示が、DB上の原稿種別の順序を使うことを確認する。
    def test_category_groups_use_database_group_order(self):
        form = SearchDetailForm()
        groups_by_name = {
            group['name']: group['categories']
            for group in form.category_groups
        }

        self.assertEqual(
            [category['name'] for category in groups_by_name['テスト原稿種別A']],
            ['テストカテゴリA'],
        )
        self.assertEqual(
            [category['name'] for category in groups_by_name['テスト原稿種別B']],
            ['テストカテゴリB'],
        )
        group_names = [group['name'] for group in form.category_groups]
        self.assertLess(
            group_names.index('テスト原稿種別A'),
            group_names.index('テスト原稿種別B'),
        )


# 原稿種別の未指定を、運用コマンドではなくDB制約で防ぐ。
class CategoryGroupRequirementTests(TestCase):
    # カテゴリは、原稿種別なしではDBへ保存できない。
    def test_category_group_is_required_by_the_database(self):
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='原稿種別未指定カテゴリ')


# カテゴリを絞り込むための画面操作部品を確認する。
class SearchDetailCategoryPickerTemplateTests(TestCase):
    # 詳細検索画面にカテゴリ検索UIの案内と操作部品を表示することを確認する。
    def test_detail_search_page_renders_category_picker_controls(self):
        response = self.client.get(reverse('search:SearchDetail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'カテゴリを絞り込む')
        self.assertContains(response, '複数選択は「いずれか」に一致')
        self.assertContains(response, 'カテゴリ名で絞り込む')
        self.assertContains(response, '全て選択（全カテゴリ）')
        self.assertContains(response, '全解除')
        self.assertNotContains(response, 'すべて表示')
        self.assertNotContains(response, '表示を絞る')
        self.assertContains(response, 'id="category-filter"')
        self.assertContains(response, 'id="category-select-all"')
        self.assertContains(response, 'id="category-clear"')
        self.assertNotContains(response, 'id="category-show-all"')
        self.assertNotContains(response, 'data-initial-limit')
        self.assertContains(response, 'href="/static/image/favicon.ico"')
        self.assertContains(response, 'src="/static/image/tenki_top.jpg"')
        self.assertContains(response, 'src="/static/image/tenki_mail.png"')
        self.assertContains(response, '/static/js/category_picker.js')


# 巻詳細の発行管理画面と号作成の主要操作を確認する。
class PublicationAdminTests(TestCase):
    # 管理者、巻、号、記事を用意する。
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username='publication-admin',
            password='test-password',
        )
        cls.year = Year.objects.create(year=2019, volume=66)
        cls.first_issue = Month.objects.create(
            volume=cls.year,
            no=1,
            start_page=3,
        )
        Month.objects.create(volume=cls.year, no=3, start_page=113)
        cls.special_issue = Month.objects.create(
            volume=cls.year,
            no=13,
            start_page=0,
        )
        Kijis.objects.create(
            title='発行管理の記事',
            volume='66',
            no='1',
            startpage=3,
        )

    # 各テストで管理者として発行管理を開く。
    def setUp(self):
        self.client.force_login(self.user)

    # 巻の詳細に号一覧、記事数、記事追加リンクを表示する。
    def test_change_page_shows_issue_table_and_article_add_link(self):
        response = self.client.get(
            reverse('admin:search_year_change', args=(self.year.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '発行管理')
        self.assertContains(response, '第66巻（2019年）｜登録号: 1、3、13')
        self.assertContains(response, 'この号に記事を追加')
        self.assertNotContains(response, '通常号を不足分だけ作成')
        self.assertNotContains(response, '巻の情報')
        self.assertNotContains(response, 'name="_save"')
        issue_rows = response.context['issue_rows']
        first_issue = next(issue for issue in issue_rows if issue.no == 1)
        self.assertEqual(first_issue.article_count, 1)
        self.assertEqual(
            first_issue.article_add_url,
            f'{reverse("admin:list_kijis_add")}?volume=66&no=1&from_year={self.year.pk}',
        )
        self.assertEqual(
            first_issue.article_changelist_url,
            f'{reverse("admin:list_kijis_changelist")}?volume=66&no=1',
        )
        self.assertContains(response, 'この号の記事を編集')
        self.assertContains(response, '入力を破棄して元の画面に戻る')
        self.assertContains(response, 'data-discard-form')

    # 巻一覧は、既存の一覧列だけで対象の巻を選べるようにする。
    def test_year_changelist_hides_the_publication_management_column(self):
        response = self.client.get(reverse('admin:search_year_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '発行管理を開く')
        self.assertNotIn('manage_issues', response.context['cl'].list_display)

    # 巻の追加画面では、標準の巻番号・発行年の入力欄を残す。
    def test_year_add_page_keeps_standard_volume_fields(self):
        response = self.client.get(reverse('admin:search_year_add'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_volume"')
        self.assertContains(response, 'id="id_year"')
        self.assertContains(response, '入力を破棄して元の画面に戻る')

    # 管理ホームから、巻、号、記事追加・編集の主導線を確認できる。
    def test_admin_home_explains_article_operation_route(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '日常の操作')
        self.assertContains(response, 'この号に記事を追加')
        self.assertContains(response, 'この号の記事を編集')
        self.assertContains(response, reverse('admin:search_year_changelist'))

    # 巻詳細の編集リンクは、対象の巻・号の記事だけを表示する。
    def test_issue_article_edit_link_filters_to_the_selected_issue(self):
        Kijis.objects.create(
            title='別の号の記事',
            volume='66',
            no='3',
            startpage=113,
        )
        change_response = self.client.get(
            reverse('admin:search_year_change', args=(self.year.pk,))
        )
        issue_rows = change_response.context['issue_rows']
        first_issue = next(issue for issue in issue_rows if issue.no == 1)

        response = self.client.get(first_issue.article_changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '発行管理の記事')
        self.assertNotContains(response, '別の号の記事')

    # 記事がある号は、掲載先番号の変更も削除もできない。
    def test_article_issue_cannot_be_renumbered_or_deleted(self):
        change_url = reverse(
            'admin:search_month_change',
            args=(self.first_issue.pk,),
        )
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="id_volume"')
        self.assertNotContains(response, 'id="id_no"')
        self.assertNotContains(response, 'deletelink')

        delete_response = self.client.get(
            reverse('admin:search_month_delete', args=(self.first_issue.pk,))
        )
        self.assertEqual(delete_response.status_code, 403)

        response = self.client.post(
            change_url,
            {
                'volume': self.year.pk,
                'no': 2,
                'start_page': 3,
                '_save': '保存',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.first_issue.refresh_from_db()
        self.assertEqual(self.first_issue.no, 1)

    # 巻から開いた号の追加・編集フォームは、破棄後に同じ巻の発行管理へ戻る。
    def test_month_forms_discard_to_the_parent_year(self):
        parent_url = reverse('admin:search_year_change', args=(self.year.pk,))
        add_response = self.client.get(
            reverse('admin:search_month_add'),
            {'from_year': self.year.pk},
        )
        change_response = self.client.get(
            reverse('admin:search_month_change', args=(self.first_issue.pk,)),
            {'from_year': self.year.pk},
        )

        for response in (add_response, change_response):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, parent_url)
            self.assertContains(response, '入力を破棄して元の画面に戻る')
            self.assertNotContains(response, 'related-widget-wrapper-link view-related')
            self.assertNotContains(response, 'icon-viewlink.svg')
            self.assertNotContains(response, 'id="delete_id_volume"')

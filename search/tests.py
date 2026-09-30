from django import forms
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from list.models import Bunrui, Category, Kijis

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

    # 号の先頭に空欄を置き、その後に重複のない号を表示する。
    def test_issue_choices_use_distinct_numbers_from_all_volumes(self):
        form = SearchDetailForm()
        values = [value for value, _label in form.fields['n'].choices]
        self.assertEqual(values, ['', 1, 2, 13])

    # 巻と号のどちらにも、先頭に空欄が表示されることを確認する。
    def test_volume_and_issue_choices_start_with_blank(self):
        form = SearchDetailForm()
        volume_choice = list(form.fields['vol'].choices)[0]
        issue_choice = list(form.fields['n'].choices)[0]

        self.assertEqual(volume_choice, ('', ''))
        self.assertEqual(issue_choice, ('', ''))

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
        cls.unused = Category.objects.create(name='未使用カテゴリ')
        cls.most_used = Category.objects.create(name='最多カテゴリ')
        cls.second_same_count = Category.objects.create(name='Beta')
        cls.first_same_count = Category.objects.create(name='Alpha')

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


# カテゴリを絞り込むための画面操作部品を確認する。
class SearchDetailCategoryPickerTemplateTests(TestCase):
    # 詳細検索画面にカテゴリ検索UIの案内と操作部品を表示することを確認する。
    def test_detail_search_page_renders_category_picker_controls(self):
        response = self.client.get(reverse('search:SearchDetail'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'カテゴリを絞り込む')
        self.assertContains(response, '複数選択は「いずれか」に一致')
        self.assertContains(response, '全て選択')
        self.assertContains(response, '全解除')
        self.assertNotContains(response, 'すべて表示')
        self.assertNotContains(response, '表示を絞る')
        self.assertContains(response, 'id="category-filter"')
        self.assertContains(response, 'id="category-select-all"')
        self.assertContains(response, 'id="category-clear"')
        self.assertNotContains(response, 'id="category-show-all"')
        self.assertNotContains(response, 'data-initial-limit')
        self.assertContains(response, '/static/js/category_picker.js')


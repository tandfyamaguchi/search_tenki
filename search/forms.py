#検索画面SearchDetail.htmlのフォームを設定
from typing import NamedTuple

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Value, When

from .category_groups import build_category_groups
from .models import Year, Month
from list.models import Bunrui, Category

# 参照サイトと同じ、内容分類の階層順を定義する。
BUNRUI_DISPLAY_ORDER = (
    1,
    101, 102, 103, 104, 1041, 1042, 105, 1051, 1052, 1053,
    106, 107, 1071, 108, 1081, 109, 1091, 1092, 10921, 1093,
    1094, 110,
    2,
    201, 202, 2021, 203, 204, 205, 206, 207, 208,
    3,
    301, 302, 303, 304, 305, 306,
    4,
    401, 4011, 402, 403, 404, 405, 406, 407, 408, 409, 410,
    411, 412, 413, 414, 415,
    5,
    501, 5011, 50111, 5012, 5013, 502, 503, 504, 505, 506, 507,
    6,
    601, 602, 603, 604,
    7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
)


# 分類番号から、一階層上の分類番号を取得する。
def _get_bunrui_parent_id(bunrui_id):
    number = str(bunrui_id)
    if len(number) <= 2:
        return None
    if len(number) == 3:
        return int(number[0])
    return int(number[:-1])


# 分類の親子関係から、選択肢に付ける枝記号を作る。
def _build_bunrui_tree_prefixes():
    parent_ids = {}
    children_by_parent = {}
    display_ids = set(BUNRUI_DISPLAY_ORDER)

    # 各分類の親番号と、親ごとの子番号を整理する。
    for bunrui_id in BUNRUI_DISPLAY_ORDER:
        parent_id = _get_bunrui_parent_id(bunrui_id)
        if parent_id not in display_ids:
            continue
        parent_ids[bunrui_id] = parent_id
        children_by_parent.setdefault(parent_id, []).append(bunrui_id)

    prefixes = {}
    for bunrui_id in BUNRUI_DISPLAY_ORDER:
        parent_id = parent_ids.get(bunrui_id)
        if parent_id is None:
            prefixes[bunrui_id] = ''
            continue

        # 上位階層の縦線を、親に近いものから順に付ける。
        ancestor_lines = []
        ancestor_id = parent_id
        while ancestor_id in parent_ids:
            ancestor_parent_id = parent_ids[ancestor_id]
            siblings = children_by_parent[ancestor_parent_id]
            ancestor_lines.append(
                '  ' if ancestor_id == siblings[-1] else '│'
            )
            ancestor_id = ancestor_parent_id

        siblings = children_by_parent[parent_id]
        branch = '└' if bunrui_id == siblings[-1] else '├'
        prefixes[bunrui_id] = ''.join(reversed(ancestor_lines)) + branch

    return prefixes


BUNRUI_TREE_PREFIXES = _build_bunrui_tree_prefixes()

# 未登録の分類番号は、既知の分類に続けてID順で表示する。
BUNRUI_CHOICES = Bunrui.objects.annotate(
    bunrui_display_order=Case(
        *(
            When(id=bunrui_id, then=Value(position))
            for position, bunrui_id in enumerate(BUNRUI_DISPLAY_ORDER)
        ),
        default=Value(len(BUNRUI_DISPLAY_ORDER)),
        output_field=IntegerField(),
    )
).order_by('bunrui_display_order', 'id')
# カテゴリは登録IDの昇順で表示する。
CATEGORY_CHOICES = Category.objects.order_by('id')
VOLUME_CHOICES = Year.objects.all().order_by('id').reverse()
ORDER_CHOICES = ((0, "降順"),(1, "昇順"))
PAGES_CHOICES = ((10,10),(30,30),(50,50),(100,100))


# 検索式を、ORごとの必須語群と除外語に分けて保持する。
class SearchExpression(NamedTuple):
    positive_groups: tuple
    excluded_terms: tuple


# 検索式中の連続する空白を半角空白1つにそろえる。
def _normalize_search_expression(value):
    return ' '.join(value.split())


# 詳細検索用の検索式を、必須語群と除外語へ分解して検証する。
def parse_search_expression(value):
    normalized_value = _normalize_search_expression(value)
    if not normalized_value:
        return SearchExpression(positive_groups=(), excluded_terms=())

    positive_groups = []
    current_group = []
    excluded_terms = []

    for token in normalized_value.split(' '):
        # 独立した大文字のORだけを、検索語群を分ける演算子として扱う。
        if token == 'OR':
            if not current_group:
                raise ValidationError(
                    'OR は検索語と検索語の間に入力してください。'
                )
            positive_groups.append(tuple(current_group))
            current_group = []
            continue

        # 除外検索の記号だけでは、除外する検索語が指定されていない。
        if token == '-':
            raise ValidationError(
                '「-」の後に除外する検索語を入力してください。'
            )

        # 二重ハイフンは、意図しない除外検索になるため受け付けない。
        if token.startswith('--'):
            raise ValidationError(
                '「--」で始まる検索語は使用できません。'
            )

        # 語頭の半角ハイフンは、すべてのOR候補に共通する除外語とする。
        if token.startswith('-'):
            excluded_terms.append(token[1:])
            continue

        current_group.append(token)

    if current_group:
        positive_groups.append(tuple(current_group))
    elif positive_groups:
        raise ValidationError(
            'OR は検索語と検索語の間に入力してください。'
        )

    return SearchExpression(
        positive_groups=tuple(positive_groups),
        excluded_terms=tuple(excluded_terms),
    )


# 内容分類を、階層記号と分類番号を付けて表示する。
class BunruiChoiceField(forms.ModelChoiceField):
    # 内容分類の選択肢に、枝記号、番号、名称を表示する。
    def label_from_instance(self, obj):
        prefix = BUNRUI_TREE_PREFIXES.get(obj.id, '')
        return f'{prefix}{obj.id}. {obj.name}'


# 複数選択から空欄を除き、空欄だけの場合は未選択にする。
def _remove_blank_choice(value):
    if value == '':
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item != '']
    return value


# 空文字を未選択として受け付けるモデルの複数選択欄。
class ClearableModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    # チェックボックス一覧に空の選択肢を表示しない。
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_label = None

    # 空欄が選ばれた場合は、モデルを選択していない状態にする。
    def clean(self, value):
        return super().clean(_remove_blank_choice(value))


# 数値の複数選択欄で、空欄を未選択として扱う。
class ClearableTypedMultipleChoiceField(forms.TypedMultipleChoiceField):
    # 空欄が選ばれた場合は、数値を選択していない状態にする。
    def clean(self, value):
        return super().clean(_remove_blank_choice(value))


# 詳細検索画面の入力フォームを定義する。
class SearchDetailForm(forms.Form):
    bun = BunruiChoiceField(label='内容分類', widget=forms.Select, queryset=BUNRUI_CHOICES, required=False,)
    categ = forms.ModelMultipleChoiceField(label='カテゴリ', widget=forms.CheckboxSelectMultiple, queryset=CATEGORY_CHOICES, required=False,)
    title = forms.CharField(label='タイトル', widget=forms.TextInput(), max_length=20, required=False,)
    author = forms.CharField(label='著者', widget=forms.TextInput(), max_length=20, required=False,)
    vol = ClearableModelMultipleChoiceField(
        label='巻',
        widget=forms.CheckboxSelectMultiple(
            attrs={'data-checkbox-picker-input': 'true'},
        ),
        queryset=VOLUME_CHOICES,
        to_field_name='volume',
        required=False,
    )
    # 号はMonthではなく、重複しない整数として選択する。
    n = ClearableTypedMultipleChoiceField(
        label='号',
        widget=forms.CheckboxSelectMultiple(
            attrs={'data-checkbox-picker-input': 'true'},
        ),
        choices=(),
        coerce=int,
        required=False,
    )
    word = forms.CharField(label='キーワード', widget=forms.TextInput(), max_length=20, required=False,)
    order = forms.ChoiceField(label='巻の並び順', widget=forms.Select, choices = ORDER_CHOICES, required=False,initial=0)
    pages = forms.TypedChoiceField(label='ページあたり表示件数', widget=forms.Select, choices = PAGES_CHOICES, coerce=int, required=False, initial=30)

    # フォーム生成時に、全巻の号選択肢を設定する。
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 選択済みのカテゴリを反映した、原稿種別ごとの表示データを作る。
        selected_category_ids = self['categ'].value() or ()
        if isinstance(selected_category_ids, str):
            selected_category_ids = (selected_category_ids,)
        self.category_groups = build_category_groups(
            self.fields['categ'].queryset,
            selected_category_ids,
        )
        # 全巻に存在する号を、重複を除いて昇順で表示する。
        issue_numbers = (
            Month.objects.order_by('no')
            .values_list('no', flat=True)
            .distinct()
        )
        # 未チェックで号を未選択にできるため、空の候補は表示しない。
        self.fields['n'].choices = [
            (number, number) for number in issue_numbers
        ]

    # 並び順が未指定の場合は、降順を返す。
    def clean_order(self):
        return self.cleaned_data.get('order') or '0'

    # 表示件数が未指定の場合は、30件を返す。
    def clean_pages(self):
        return self.cleaned_data.get('pages') or 30

    # 検索式を検証し、表示にも使える正規化済み文字列を返す。
    def _clean_search_expression_field(self, field_name):
        value = self.cleaned_data[field_name]
        parse_search_expression(value)
        return _normalize_search_expression(value)

    # タイトル検索式を検証して正規化する。
    def clean_title(self):
        return self._clean_search_expression_field('title')

    # 著者検索式を検証して正規化する。
    def clean_author(self):
        return self._clean_search_expression_field('author')

    # キーワード検索式を検証して正規化する。
    def clean_word(self):
        return self._clean_search_expression_field('word')

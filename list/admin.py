from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html

from search.models import Month, Year

from .models import (
    ArticleAuthor,
    Author,
    Bunrui,
    Category,
    CategoryGroup,
    Kijis,
    Keyword,
)


# 記事のカテゴリでは、選択解除用のSelect2の✖を表示しない。
class ArticleCategoryAutocompleteSelect(AutocompleteSelect):
    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs['data-allow-clear'] = 'false'
        return attrs


# 記事入力用の巻・号選択肢と整合性を管理する。
class ArticleAdminForm(forms.ModelForm):
    volume = forms.ChoiceField(label='巻', choices=(), required=False)
    no = forms.ChoiceField(label='号', choices=(), required=False)

    # 記事の入力欄を日常運用向けの順序と日本語表示にする。
    class Meta:
        model = Kijis
        fields = (
            'title',
            'volume',
            'no',
            'startpage',
            'pdf',
            'category',
            'bunrui',
            'keyword',
        )
        labels = {
            'title': '題名',
            'startpage': '記事の開始頁',
            'pdf': 'PDFファイル名',
            'category': 'カテゴリ',
            'bunrui': '内容分類',
            'keyword': 'キーワード',
        }
        help_texts = {
            'startpage': '号の開始頁ではなく、この記事が始まる頁を入力します。0も入力できます。',
            'pdf': '公開済みPDFのファイル名または相対パスを入力します。ファイルのアップロードは行いません。',
        }
        widgets = {
            'title': forms.TextInput(attrs={'size': 60}),
            'pdf': forms.TextInput(attrs={'size': 50}),
        }

    # 巻・号の候補を切り替えるJavaScriptを入力画面だけで読み込む。
    class Media:
        js = ('list/js/article_admin.js',)

    # フォームごとに、発行管理の現在値から選択肢を作る。
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['volume'].choices = self._volume_choices()
        self.fields['no'].choices = self._issue_choices()
        self.fields['volume'].help_text = (
            '先に巻を選択すると、この巻に登録済みの号だけを選べます。'
        )
        self.fields['no'].help_text = (
            '巻を選択すると候補が絞り込まれます。巻・号の組合せは保存時にも確認されます。'
        )
        self.fields['no'].widget.attrs['data-issue-url'] = reverse(
            'admin:list_kijis_publication_issues'
        )

        # 新規記事には、公開検索に必要な基本情報を必須にする。
        if not self.instance.pk:
            self.fields['title'].required = True
            self.fields['startpage'].required = True
            self.fields['startpage'].widget.attrs['min'] = 0

        self._add_legacy_publication_choices()

    # 巻番号と発行年をまとめて表示する選択肢を作る。
    def _volume_choices(self):
        choices = [('', '巻を選択')]
        choices.extend(
            (
                str(year.volume),
                f'第{year.volume}巻（{year.year}年）',
            )
            for year in Year.objects.order_by('-volume')
        )
        return choices

    # JavaScriptが無効でも選べる、全巻に存在する号番号の選択肢を作る。
    def _issue_choices(self):
        issue_numbers = (
            Month.objects.order_by('no')
            .values_list('no', flat=True)
            .distinct()
        )
        return [('', '号を選択')] + [
            (str(issue_number), f'{issue_number}号')
            for issue_number in issue_numbers
        ]

    # 発行管理にない既存の巻・号を、変更画面で保持できるようにする。
    def _add_legacy_publication_choices(self):
        if not self.instance.pk:
            return

        volume = self.instance.volume or ''
        issue_number = self.instance.no or ''
        volume_choices = list(self.fields['volume'].choices)
        issue_choices = list(self.fields['no'].choices)
        volume_values = {value for value, _label in volume_choices}
        issue_values = {value for value, _label in issue_choices}
        publication_exists = self._publication_exists(volume, issue_number)

        # 正式な組合せで、現在の表記も選択肢にある場合は追加処理を行わない。
        if (
            publication_exists
            and volume in volume_values
            and issue_number in issue_values
        ):
            return

        if volume and volume not in volume_values:
            volume_choices.insert(
                1,
                (volume, f'現在の値: 第{volume}巻（発行管理に未登録）'),
            )
        if issue_number and issue_number not in issue_values:
            issue_choices.insert(
                1,
                (issue_number, f'現在の値: {issue_number}号（この巻には未登録）'),
            )

        self.fields['volume'].choices = volume_choices
        self.fields['no'].choices = issue_choices
        self.fields['no'].widget.attrs['data-legacy-pair'] = 'true'
        self.fields['no'].widget.attrs['data-legacy-volume'] = volume
        self.fields['no'].widget.attrs['data-legacy-issue'] = issue_number
        if publication_exists:
            self.fields['no'].help_text = (
                '発行管理と表記が異なる既存の巻・号です。変更しない場合はそのまま保存できます。'
                '変更する場合は、登録済みの巻と号を選択してください。'
            )
        else:
            self.fields['no'].help_text = (
                '発行管理にない既存の巻・号です。変更しない場合はそのまま保存できます。'
                '変更する場合は、登録済みの巻と号を選択してください。'
            )

    # 巻番号と号番号の組が発行管理に登録されているか確認する。
    @staticmethod
    def _publication_exists(volume, issue_number):
        if not volume or not issue_number:
            return False
        try:
            volume_number = int(volume)
            issue_number = int(issue_number)
        except (TypeError, ValueError):
            return False
        return Month.objects.filter(
            volume__volume=volume_number,
            no=issue_number,
        ).exists()

    # 既存記事の巻・号を変更していないか確認する。
    def _is_unchanged_publication(self, volume, issue_number):
        if not self.instance.pk:
            return False
        return (
            volume == (self.instance.volume or '')
            and issue_number == (self.instance.no or '')
        )

    # 新規記事は有効な巻・号を必須にし、既存の例外値だけは保持を許可する。
    def clean(self):
        cleaned_data = super().clean()
        volume = cleaned_data.get('volume') or ''
        issue_number = cleaned_data.get('no') or ''
        start_page = cleaned_data.get('startpage')

        # 新規記事では、実在しない負の頁を保存させない。
        if not self.instance.pk and start_page is not None and start_page < 0:
            self.add_error('startpage', '記事の開始頁は0以上で入力してください。')

        if self._is_unchanged_publication(volume, issue_number):
            # ChoiceFieldの空値で、旧データのNULLを空文字へ置き換えない。
            if self.instance.volume is None and not volume:
                cleaned_data['volume'] = None
            if self.instance.no is None and not issue_number:
                cleaned_data['no'] = None
            return cleaned_data

        if not volume:
            self.add_error('volume', '巻を選択してください。')
        if not issue_number:
            self.add_error('no', '号を選択してください。')
        if volume and issue_number and not self._publication_exists(
            volume,
            issue_number,
        ):
            self.add_error(
                'no',
                '選択した巻にこの号は登録されていません。',
            )

        return cleaned_data


# 記事ごとの著者名と公開表示順を入力するフォームを定義する。
class ArticleAuthorInlineForm(forms.ModelForm):
    display_order = forms.IntegerField(
        label='表示順',
        min_value=1,
        help_text='公開時の並び順を1から指定します。',
    )

    # 著者と表示順だけを記事画面で編集できるようにする。
    class Meta:
        model = ArticleAuthor
        fields = ('display_order', 'author')


# 同じ著者や同じ表示順を誤って入力しないようにする。
class ArticleAuthorInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        author_ids = set()
        display_orders = set()

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue

            author = form.cleaned_data.get('author')
            display_order = form.cleaned_data.get('display_order')
            if author is None:
                continue

            if author.pk in author_ids:
                form.add_error('author', '同じ著者は1回だけ指定してください。')
            else:
                author_ids.add(author.pk)

            if display_order in display_orders:
                form.add_error('display_order', '同じ表示順は指定できません。')
            elif display_order is not None:
                display_orders.add(display_order)


# 記事の著者と表示順を表形式で追加・削除する。
class ArticleAuthorInline(admin.TabularInline):
    model = ArticleAuthor
    form = ArticleAuthorInlineForm
    formset = ArticleAuthorInlineFormSet
    autocomplete_fields = ('author',)
    fields = ('display_order', 'author')
    extra = 1
    ordering = ('display_order', 'id')
    verbose_name = '著者'
    verbose_name_plural = '著者（公開表示順）'

    # 使用中の著者は削除できないため、403になる関連削除の✖を表示しない。
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if (
            db_field.name == 'author'
            and formfield is not None
            and hasattr(formfield.widget, 'can_delete_related')
        ):
            formfield.widget.can_delete_related = False
        return formfield


# 記事で使う関連データを、使用中の記事数とともに管理する。
class ArticleReferenceAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)
    list_display = ('name', 'used_article_count', 'delete_link')
    list_display_links = ('name',)
    article_relation_name = None

    # 削除権限がない利用者には、実行できない削除リンクを表示しない。
    def get_list_display(self, request):
        if self.has_delete_permission(request):
            return self.list_display
        return tuple(
            field for field in self.list_display if field != 'delete_link'
        )

    # 使用中の記事数をまとめて取得し、一覧ごとの追加検索を防ぐ。
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            admin_article_count=Count(
                self.article_relation_name,
                distinct=True,
            )
        )

    # 使用中の記事数を管理画面で分かるようにする。
    @admin.display(description='使用中の記事数', ordering='admin_article_count')
    def used_article_count(self, obj):
        article_count = getattr(obj, 'admin_article_count', None)
        if article_count is None:
            article_count = self._article_relation(obj).count()
        return article_count

    # 関連データが使われている記事を取得する。
    def _article_relation(self, obj):
        return getattr(obj, self.article_relation_name)

    # 未使用の関連データだけに、削除確認画面へのリンクを表示する。
    @admin.display(description='操作')
    def delete_link(self, obj):
        article_count = getattr(obj, 'admin_article_count', None)
        if article_count is None:
            article_count = self._article_relation(obj).count()
        if article_count:
            return '使用中'
        delete_url = reverse(
            f'admin:{self.opts.app_label}_{self.opts.model_name}_delete',
            args=(obj.pk,),
        )
        return format_html('<a href="{}">削除</a>', delete_url)

    # 使用中の関連データを削除して、既存記事の表示を失わせない。
    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or not self._article_relation(obj).exists()

    # 一括削除では使用中の関連データを混ぜる事故を防ぐ。
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

# カテゴリを原稿種別とともに管理する。
@admin.register(Category)
class CategoryAdmin(ArticleReferenceAdmin):
    article_relation_name = 'category'
    list_display = (
        'name',
        'category_group',
        'used_article_count',
        'delete_link',
    )
    list_filter = ('group',)
    # 絞り込み件数表示用の目アイコンは、カテゴリ管理では使わない。
    show_facets = admin.ShowFacets.NEVER
    list_select_related = ('group',)
    ordering = ('group__display_order', 'id')
    fields = ('name', 'group')

    # この画面で選ぶ原稿種別はカテゴリに使用されるため、403になる削除の✖を表示しない。
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if (
            db_field.name == 'group'
            and formfield is not None
            and hasattr(formfield.widget, 'can_delete_related')
        ):
            formfield.widget.can_delete_related = False
        return formfield

    # 必須の原稿種別を一覧の列として表示する。
    @admin.display(description='原稿種別', ordering='group__display_order')
    def category_group(self, obj):
        return obj.group


# 内容分類を名称と使用中の記事数で管理する。
@admin.register(Bunrui)
class BunruiAdmin(ArticleReferenceAdmin):
    article_relation_name = 'bunrui'


# 未使用の著者名を確認・削除できる管理画面を登録する。
@admin.register(Author)
class AuthorAdmin(ArticleReferenceAdmin):
    article_relation_name = 'article_author_links'
    list_display_links = None

    # 既存の著者名は表記揺れを避けるため編集せず、削除・追加だけを扱う。
    def has_change_permission(self, request, obj=None):
        return False


# キーワードを名称と使用中の記事数で管理する。
@admin.register(Keyword)
class KeywordAdmin(ArticleReferenceAdmin):
    article_relation_name = 'keyword'


# 原稿種別を表示順とともに管理する。
@admin.register(CategoryGroup)
class CategoryGroupAdmin(admin.ModelAdmin):
    list_display = ('display_order', 'name', 'category_count')
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('display_order', 'id')
    fields = ('name', 'display_order')

    # 原稿種別ごとのカテゴリ数をまとめて取得する。
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            admin_category_count=Count('categories')
        )

    # 原稿種別に属するカテゴリ数を表示する。
    @admin.display(description='カテゴリ数', ordering='admin_category_count')
    def category_count(self, obj):
        category_count = getattr(obj, 'admin_category_count', None)
        if category_count is None:
            category_count = obj.categories.count()
        return category_count

    # カテゴリが属する原稿種別は削除できないようにする。
    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or not obj.categories.exists()

    # 一括削除ではカテゴリを持つ原稿種別を混ぜる事故を防ぐ。
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


# 記事を日常運用するための追加・検索画面を定義する。
@admin.register(Kijis)
class KijisAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    inlines = (ArticleAuthorInline,)
    autocomplete_fields = ('category', 'bunrui', 'keyword')
    list_display = (
        'id',
        'article_title',
        'publication',
        'article_start_page',
        'article_category',
        'pdf_filename',
    )
    list_display_links = ('article_title',)
    list_select_related = ('category',)
    search_fields = (
        'title',
        'author__name',
        'keyword__name',
        '=volume',
        '=no',
    )
    ordering = ('-id',)
    list_per_page = 50
    save_on_top = True
    fieldsets = (
        (
            '記事情報',
            {
                'fields': ('title', 'category'),
            },
        ),
        (
            '掲載情報',
            {
                'fields': (('volume', 'no', 'startpage'), 'pdf'),
                'description': (
                    '先に巻を選び、続いて登録済みの号を選択します。'
                    '記事の開始頁は、号の開始頁とは別に入力してください。'
                ),
            },
        ),
        (
            '関連情報',
            {
                'fields': ('bunrui', 'keyword'),
                'description': (
                    '入力欄に文字を入れると、既存の候補を検索できます。'
                    '著者は下の表で公開表示順とともに指定します。'
                ),
            },
        ),
    )
    readonly_fields = ('article_id',)

    # 記事一覧で題名が空の旧データも区別して表示する。
    @admin.display(
        description='題名',
        ordering='title',
        empty_value='（題名なし）',
    )
    def article_title(self, obj):
        return obj.title

    # 巻・号を1列にまとめて表示する。
    @admin.display(description='掲載巻・号')
    def publication(self, obj):
        if not obj.volume or not obj.no:
            return '未設定'
        return f'第{obj.volume}巻 {obj.no}号'

    # 記事の開始頁を日本語の見出しで表示する。
    @admin.display(
        description='記事の開始頁',
        ordering='startpage',
        empty_value='未設定',
    )
    def article_start_page(self, obj):
        return obj.startpage

    # カテゴリ未設定の記事も一覧で判別できるようにする。
    @admin.display(
        description='カテゴリ',
        ordering='category__name',
        empty_value='未設定',
    )
    def article_category(self, obj):
        return obj.category

    # PDF未設定の記事も一覧で判別できるようにする。
    @admin.display(
        description='PDFファイル名',
        ordering='pdf',
        empty_value='未設定',
    )
    def pdf_filename(self, obj):
        return obj.pdf

    # 変更画面で記事IDを確認できるようにする。
    @admin.display(description='記事ID')
    def article_id(self, obj):
        return obj.pk

    # 既存記事の変更画面だけに、記事IDを表示する。
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None:
            return fieldsets
        return fieldsets + (
            (
                '記録',
                {
                    'fields': ('article_id',),
                },
            ),
        )

    # カテゴリだけは、既存選択を空に戻すSelect2の✖を表示しない。
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'category':
            kwargs['widget'] = ArticleCategoryAutocompleteSelect(
                db_field,
                self.admin_site,
                using=kwargs.get('using'),
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # 記事のカテゴリ選択横に、カテゴリ自体を削除する✖操作を表示しない。
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'category' and formfield is not None:
            formfield.widget.can_delete_related = False
        return formfield

    # 巻の発行管理から追加した記事は、未保存入力を破棄すると親の巻へ戻す。
    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url='',
        obj=None,
    ):
        combined_context = dict(context)
        parent_year = self._get_parent_year_for_discard(request, obj)
        if parent_year is not None:
            combined_context['discard_url'] = reverse(
                'admin:search_year_change',
                args=(parent_year.pk,),
            )
        return super().render_change_form(
            request,
            combined_context,
            add,
            change,
            form_url,
            obj,
        )

    # 画面の巻と一致する親巻だけを、破棄後の戻り先として使う。
    @staticmethod
    def _get_parent_year_for_discard(request, obj):
        parent_year_id = request.GET.get('from_year')
        if not parent_year_id:
            return None
        parent_year = Year.objects.filter(pk=parent_year_id).first()
        if parent_year is None:
            return None

        article_volume = (
            obj.volume if obj is not None else request.GET.get('volume')
        )
        if article_volume != str(parent_year.volume):
            return None
        return parent_year

    # 巻番号に属する号を、画面操作用のJSONとして返すURLを追加する。
    def get_urls(self):
        custom_urls = [
            path(
                'publication-issues/',
                self.admin_site.admin_view(self.publication_issues_view),
                name='list_kijis_publication_issues',
            ),
        ]
        return custom_urls + super().get_urls()

    # 選択中の巻に登録された号だけを番号順で返す。
    def publication_issues_view(self, request):
        if not (
            self.has_add_permission(request)
            or self.has_change_permission(request)
        ):
            raise PermissionDenied

        try:
            volume = int(request.GET.get('volume', ''))
        except (TypeError, ValueError):
            return JsonResponse({'issues': []})

        issues = Month.objects.filter(volume__volume=volume).order_by('no')
        return JsonResponse(
            {
                'issues': [
                    {
                        'number': issue.no,
                        'start_page': issue.start_page,
                    }
                    for issue in issues
                ],
            }
        )

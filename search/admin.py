from urllib.parse import urlencode

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import (
    CharField,
    Count,
    IntegerField,
    OuterRef,
    Prefetch,
    Subquery,
    Value,
)
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponseRedirect
from django.urls import reverse

from list.models import Kijis

from .models import Month, Year


# 号番号を、管理画面で読みやすい連続範囲に整形する。
def format_issue_numbers(issue_numbers):
    numbers = sorted(set(issue_numbers))
    if not numbers:
        return '未登録'

    ranges = []
    range_start = numbers[0]
    previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append(
            str(range_start) if range_start == previous else f'{range_start}〜{previous}'
        )
        range_start = number
        previous = number
    ranges.append(
        str(range_start) if range_start == previous else f'{range_start}〜{previous}'
    )
    return '、'.join(ranges)


# 巻・号の組に記事があるかを、記事側の既存文字列値で確認する。
def has_articles_for_publication(volume_number, issue_number):
    return Kijis.objects.filter(
        volume=str(volume_number),
        no=str(issue_number),
    ).exists()


# 巻の入力欄を管理画面向けの日本語表示にし、使用中の巻番号を保護する。
class YearAdminForm(forms.ModelForm):
    # 巻の入力欄と表示名を定義する。
    class Meta:
        model = Year
        fields = ('volume', 'year')
        labels = {
            'volume': '巻番号',
            'year': '発行年',
        }

    # 既存の号や記事との対応が変わる巻番号の変更を防ぐ。
    def clean_volume(self):
        volume = self.cleaned_data['volume']
        if not self.instance.pk or volume == self.instance.volume:
            return volume
        if (
            self.instance.month_set.exists()
            or Kijis.objects.filter(volume=str(self.instance.volume)).exists()
        ):
            raise forms.ValidationError(
                '登録済みの号または記事があるため、巻番号は変更できません。'
            )
        return volume


# 号の入力欄を管理画面向けの日本語表示にし、記事の掲載先を保護する。
class MonthAdminForm(forms.ModelForm):
    # 号の入力欄と表示名を定義する。
    class Meta:
        model = Month
        fields = ('volume', 'no', 'start_page')
        labels = {
            'volume': '巻',
            'no': '号',
            'start_page': '開始頁',
        }
        help_texts = {
            'start_page': '0も入力できます。',
        }

    # 変更前の巻・号を保存して、入力後の値との比較に使う。
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_volume_number = None
        self._original_issue_number = None
        if self.instance.pk:
            self._original_volume_number = self.instance.volume.volume
            self._original_issue_number = self.instance.no

    # 記事が登録済みの号は、巻・号番号だけ変更させない。
    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk:
            return cleaned_data
        volume = cleaned_data.get('volume')
        issue_number = cleaned_data.get('no')
        publication_changed = (
            volume is not None
            and issue_number is not None
            and (
                volume.volume != self._original_volume_number
                or issue_number != self._original_issue_number
            )
        )
        if publication_changed and has_articles_for_publication(
            self._original_volume_number,
            self._original_issue_number,
        ):
            raise forms.ValidationError(
                '記事が登録済みのため、この号の巻番号・号番号は変更できません。'
            )
        return cleaned_data


# 号を巻の詳細画面から追加・編集するための非表示管理画面を定義する。
@admin.register(Month)
class MonthAdmin(admin.ModelAdmin):
    form = MonthAdminForm
    fields = ('volume', 'no', 'start_page')
    ordering = ('volume__volume', 'no')

    # 巻画面を主入口にするため、号を管理トップのメニューには表示しない。
    def has_module_permission(self, request):
        return False

    # 親の巻から追加した場合だけ、選べる巻を親の巻に限定する。
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'volume':
            parent_year = self._get_parent_year(request)
            if parent_year is not None:
                kwargs['queryset'] = Year.objects.filter(pk=parent_year.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # 親の巻から新規追加する場合の初期値を設定する。
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        parent_year = self._get_parent_year(request)
        if parent_year is not None:
            initial['volume'] = parent_year.pk
        return initial

    # 記事がある号では、掲載先そのものを読み取り専用にする。
    def get_readonly_fields(self, request, obj=None):
        if obj is not None and has_articles_for_publication(
            obj.volume.volume,
            obj.no,
        ):
            return ('volume', 'no')
        return ()

    # 記事がある号を削除して、記事の掲載先だけを失うことを防ぐ。
    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or not has_articles_for_publication(
            obj.volume.volume,
            obj.no,
        )

    # 一括削除では、記事を含む号が混ざる事故を防ぐ。
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    # 直接削除の直前にも、記事との対応を再確認する。
    def delete_model(self, request, obj):
        if has_articles_for_publication(obj.volume.volume, obj.no):
            raise PermissionDenied
        super().delete_model(request, obj)

    # 巻画面から開いた場合に、保存後も同じ発行管理画面へ戻す。
    def response_add(self, request, obj, post_url_continue=None):
        redirect_response = self._parent_year_redirect(request, obj, '号を追加しました。')
        if redirect_response is not None:
            return redirect_response
        return super().response_add(request, obj, post_url_continue)

    # 巻画面から開いた場合に、編集後も同じ発行管理画面へ戻す。
    def response_change(self, request, obj):
        redirect_response = self._parent_year_redirect(request, obj, '号を更新しました。')
        if redirect_response is not None:
            return redirect_response
        return super().response_change(request, obj)

    # 巻の発行管理から開いた号フォームでは、未保存入力の破棄先を親の巻にする。
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
        parent_year = self._get_parent_year(request)
        if parent_year is not None and (
            obj is None or parent_year.pk == obj.volume_id
        ):
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

    # URLの親巻番号から、戻り先の巻を取得する。
    @staticmethod
    def _get_parent_year(request):
        parent_year_id = request.GET.get('from_year')
        if not parent_year_id:
            return None
        return Year.objects.filter(pk=parent_year_id).first()

    # 親巻が指定された場合だけ、成功メッセージ付きで詳細画面へ戻る。
    def _parent_year_redirect(self, request, obj, message):
        parent_year = self._get_parent_year(request)
        if parent_year is None or parent_year.pk != obj.volume_id:
            return None
        self.message_user(request, message, messages.SUCCESS)
        return HttpResponseRedirect(
            reverse('admin:search_year_change', args=(parent_year.pk,))
        )


# 巻を起点に、号と記事追加を管理する主画面を定義する。
@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    form = YearAdminForm
    change_form_template = 'admin/search/year/change_form.html'
    # 巻の追加画面は、標準の入力フォームをそのまま使う。
    add_form_template = 'admin/change_form.html'
    list_display = (
        'volume_number',
        'publication_year',
        'registered_issue_count',
        'registered_issue_numbers',
    )
    list_display_links = ('volume_number',)
    search_fields = ('=volume', '=year')
    ordering = ('-volume',)
    list_per_page = 50
    add_fieldsets = (
        (
            '巻の情報',
            {
                'fields': (('volume', 'year'),),
            },
        ),
    )

    # 新しい巻を追加するときだけ、巻番号と発行年の入力欄を表示する。
    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return ()

    # 巻一覧用に号数と号番号をまとめて取得し、行ごとの追加検索を防ぐ。
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(admin_issue_count=Count('month'))
            .prefetch_related(
                Prefetch(
                    'month_set',
                    queryset=Month.objects.order_by('no'),
                    to_attr='admin_ordered_months',
                ),
            )
        )

    # 巻の変更画面に、発行管理用の号一覧を追加する。
    def change_view(self, request, object_id, form_url='', extra_context=None):
        year = self.get_object(request, object_id)
        publication_context = {}
        if year is not None:
            publication_context = self._publication_context(request, year)
        combined_context = dict(extra_context or {})
        combined_context.update(publication_context)
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=combined_context,
        )

    # 巻詳細の号一覧、操作リンク、権限情報をまとめる。
    def _publication_context(self, request, year):
        month_admin = self.admin_site._registry[Month]
        article_admin = self.admin_site._registry.get(Kijis)
        can_view_articles = (
            article_admin is not None
            and article_admin.has_view_or_change_permission(request)
        )
        can_add_articles = (
            article_admin is not None
            and article_admin.has_add_permission(request)
        )
        can_change_articles = (
            article_admin is not None
            and article_admin.has_change_permission(request)
        )
        can_add_issues = month_admin.has_add_permission(request)
        can_change_issues = month_admin.has_change_permission(request)
        issue_rows = self._issue_rows(year, can_view_articles)
        registered_issue_numbers = [issue.no for issue in issue_rows]
        for issue in issue_rows:
            issue.change_url = (
                f"{reverse('admin:search_month_change', args=(issue.pk,))}?"
                f"{urlencode({'from_year': year.pk})}"
            )
            # 記事追加の破棄後に戻る親巻も、掲載先とともにURLへ渡す。
            article_add_parameters = {
                'volume': year.volume,
                'no': issue.no,
                'from_year': year.pk,
            }
            issue.article_add_url = (
                f"{reverse('admin:list_kijis_add')}?"
                f'{urlencode(article_add_parameters)}'
            )
            # この号に属する記事だけを一覧にし、題名から編集画面へ進める。
            issue.article_changelist_url = (
                f"{reverse('admin:list_kijis_changelist')}?"
                f"{urlencode({'volume': year.volume, 'no': issue.no})}"
            )
        return {
            'issue_rows': issue_rows,
            'issue_summary': format_issue_numbers(registered_issue_numbers),
            'can_view_articles': can_view_articles,
            'can_add_articles': can_add_articles,
            'can_change_articles': can_change_articles,
            'can_change_issues': can_change_issues,
            'add_issue_url': self._month_add_url(year) if can_add_issues else None,
        }

    # 記事数を必要な場合だけ相関サブクエリで集計して、N+1を防ぐ。
    @staticmethod
    def _issue_rows(year, include_article_count):
        issue_queryset = Month.objects.filter(volume=year).order_by('no')
        if not include_article_count:
            return list(issue_queryset)
        article_count_query = (
            Kijis.objects.filter(
                volume=Cast(
                    OuterRef('volume__volume'),
                    output_field=CharField(),
                ),
                no=Cast(OuterRef('no'), output_field=CharField()),
            )
            .order_by()
            .values('volume', 'no')
            .annotate(total=Count('pk'))
            .values('total')[:1]
        )
        return list(
            issue_queryset.annotate(
                article_count=Coalesce(
                    Subquery(article_count_query, output_field=IntegerField()),
                    Value(0),
                )
            )
        )

    # 号追加画面へのURLに、戻り先となる親の巻を付ける。
    @staticmethod
    def _month_add_url(year):
        return (
            f"{reverse('admin:search_month_add')}?"
            f"{urlencode({'from_year': year.pk})}"
        )

    # 巻番号を一覧の見出しと並び替えに使える列として表示する。
    @admin.display(description='巻番号', ordering='volume')
    def volume_number(self, obj):
        return obj.volume

    # 発行年を一覧の見出しと並び替えに使える列として表示する。
    @admin.display(description='発行年', ordering='year')
    def publication_year(self, obj):
        return obj.year

    # 各巻に登録済みの号数を表示する。
    @admin.display(description='登録号数', ordering='admin_issue_count')
    def registered_issue_count(self, obj):
        return obj.admin_issue_count

    # 各巻に登録済みの号番号を昇順・連続範囲で表示する。
    @admin.display(description='登録済みの号')
    def registered_issue_numbers(self, obj):
        ordered_months = getattr(obj, 'admin_ordered_months', None)
        if ordered_months is None:
            ordered_months = obj.month_set.order_by('no')
        return format_issue_numbers([issue.no for issue in ordered_months])

    # 巻を削除すると旧記事の掲載先を失うため、管理画面では削除しない。
    def has_delete_permission(self, request, obj=None):
        return False


# admin全体で発行管理の入口を分かりやすく表示する。
admin.site.site_header = '天気記事検索 管理'
admin.site.site_title = '天気記事検索 管理'
admin.site.index_title = '管理メニュー'
# 管理ホームに、記事を追加・編集する主入口を案内するテンプレートを使う。
admin.site.index_template = 'admin/search/index.html'

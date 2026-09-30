from django import forms
from django.contrib import admin
from django.db.models import Count, Prefetch
from django.urls import reverse
from django.utils.html import format_html

from .models import Month, Year


# 巻の入力欄を管理画面向けの日本語表示にする。
class YearAdminForm(forms.ModelForm):
    # 巻の入力欄と表示名を定義する。
    class Meta:
        model = Year
        fields = ('volume', 'year')
        labels = {
            'volume': '巻番号',
            'year': '発行年',
        }


# 号の入力欄を管理画面向けの日本語表示にする。
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


# 巻の編集画面で、その巻に属する号だけを表形式で編集する。
class MonthInline(admin.TabularInline):
    model = Month
    fk_name = 'volume'
    form = MonthAdminForm
    fields = ('no', 'start_page')
    extra = 1
    ordering = ('no',)
    verbose_name = '号'
    verbose_name_plural = 'この巻の号'


# 巻を起点に号を管理する主画面を定義する。
@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    form = YearAdminForm
    inlines = (MonthInline,)
    list_display = (
        'volume_number',
        'publication_year',
        'registered_issue_count',
        'registered_issue_numbers',
        'manage_issues',
    )
    list_display_links = ('volume_number',)
    search_fields = ('=volume', '=year')
    ordering = ('-volume',)
    list_per_page = 50
    fieldsets = (
        (
            '巻の情報',
            {
                'fields': (('volume', 'year'),),
                'description': (
                    '巻を登録し、この下の「この巻の号」で必要な号だけを追加・編集します。'
                ),
            },
        ),
    )

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

    # 各巻に登録済みの号番号を昇順で表示する。
    @admin.display(description='登録済みの号')
    def registered_issue_numbers(self, obj):
        ordered_months = getattr(obj, 'admin_ordered_months', None)
        if ordered_months is None:
            ordered_months = obj.month_set.order_by('no')
        issue_numbers = [
            f'{issue.no}号'
            for issue in ordered_months
        ]
        return '、'.join(issue_numbers) if issue_numbers else '未登録'

    # 対象巻の号を編集する画面への明示的なリンクを表示する。
    @admin.display(description='号を管理')
    def manage_issues(self, obj):
        change_url = reverse('admin:search_year_change', args=(obj.pk,))
        return format_html('<a href="{}">号を管理</a>', change_url)


# admin全体で発行管理の入口を分かりやすく表示する。
admin.site.site_header = '天気記事検索 管理'
admin.site.site_title = '天気記事検索 管理'
admin.site.index_title = '管理メニュー'

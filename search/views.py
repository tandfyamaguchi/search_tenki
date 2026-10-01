from django.shortcuts import get_object_or_404, render

from .forms import SearchDetailForm
from .models import Month, Year


# 発行年と巻の一覧を表示する。
def SelectYearView(request):
    years = Year.objects.order_by('-id')
    return render(request, 'search/SelectYear.html', {'list': years})


# 選択した年度IDに紐づく号を表示する。
def SelectNoView(request, year_id):
    # 存在しない年度IDは、DoesNotExistではなく404として扱う。
    year = get_object_or_404(Year, pk=year_id)
    # テンプレートでは各号の巻を参照しないため、JOINは不要である。
    issues = Month.objects.filter(volume=year).order_by('no')
    # 既存テンプレートとの互換性のため、コンテキストキーは維持する。
    return render(
        request,
        'search/SelectNo.html',
        {'list': issues, 'vol': year.volume, 'year': year.year},
    )


# 詳細検索フォームを表示する。
def SearchDetailView(request):
    form = SearchDetailForm()
    return render(request, 'search/SearchDetail.html', {'form': form})


# 著作権案内ページを表示する。
def CopyrightView(request):
    return render(request, 'search/copyright.html')

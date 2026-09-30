from django.shortcuts import get_object_or_404, render
from .models import Year, Month
from .forms import SearchDetailForm

#全ての年(volume)を取得
def SelectYearView(request):
    #Yearモデルのidを降順に並べて取得
    list=Year.objects.order_by('id').reverse()
    return render(request, "search/SelectYear.html",{'list' : list})

# 選択した年度IDに紐づく号を表示する。
def SelectNoView(request, year_id):
    # 存在しない年度IDは、DoesNotExistではなく404として扱う。
    year = get_object_or_404(Year, pk=year_id)
    # 選択した年度に属する号と開始頁を、号番号順で取得する。
    month_list = (
        Month.objects.select_related('volume')
        .filter(volume=year)
        .order_by('no')
    )
    # 年度と巻番号をテンプレートの表示用データとして渡す。
    return render(
        request,
        "search/SelectNo.html",
        {'list': month_list, 'vol': year.volume, 'year': year.year},
    )

#検索画面のフォームを表示
def SearchDetailView(request):
    form = SearchDetailForm()
    return render(request, "search/SearchDetail.html", {'form':form})

# 著作権案内ページを表示
def CopyrightView(request):
    return render(request, "search/copyright.html")

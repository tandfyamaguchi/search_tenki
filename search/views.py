from django.shortcuts import render

from .models import Year, Month
from .forms import SearchDetailForm

#全ての年(volume)を取得
def SelectYearView(request):
    #Yearモデルのidを降順に並べて取得
    list=Year.objects.order_by('id').reverse()
    return render(request, "search/SelectYear.html",{'list' : list})

#選んだ年(volume=id)での月(no)を選択
def SelectNoView(request,id):
    #Monthモデルで選んだ年のnoとstart_pageを取得
    list=Month.objects.select_related('volume').filter(volume__volume=id).all()
    #volumeの時の年を取得
    y=Year.objects.get(volume=id).year
    return render(request, "search/SelectNo.html",{'list' : list, 'vol':id, 'year':y})

#検索画面のフォームを表示
def SearchDetailView(request):
    form = SearchDetailForm()
    return render(request, "search/SearchDetail.html", {'form':form})

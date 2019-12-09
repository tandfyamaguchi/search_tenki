from django.shortcuts import render

from .models import Year, Month
from .forms import SearchDetailForm

#全ての年(volume)を選択
def SelectYearView(request):
    list=Year.objects.order_by('id').reverse()
    return render(request, "search/SelectYear.html",{'list' : list})

#選んだ年での月(no)を選択
def SelectNoView(request,id):
    list=Month.objects.select_related('volume').filter(volume__volume=id).all()
    return render(request, "search/SelectNo.html",{'list' : list, 'vol':id})

def SearchDetailView(request):
    form = SearchDetailForm()
    return render(request, "search/SearchDetail.html", {'form':form})

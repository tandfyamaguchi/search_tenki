from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
import logging
logger = logging.getLogger('development')

from .models import Kijis, Author, Keyword, Category
from search.models import Year, Month
from search.forms import SearchDetailForm

def ShowListView1(request,id):
    search=Month.objects.filter(id=id)[0]
    vol=search.volume.volume
    n=search.no

    #volとnoの一致するKijisを取得
    kiji_list=Kijis.objects.filter(volume=vol, no=n).order_by('startpage')

    return render(request, "list/ShowList1.html", {'kiji_list':kiji_list})


def ShowListView2(request):
    
    if request.method == 'GET':
        kiji_list = Kijis.objects.all()

        form = SearchDetailForm(request.GET)
        if form.is_valid():

            def make_query(queries):
                query = queries.pop()
                for item in queries:
                    query |= item
                return query

            bun=request.GET.get("bun")
            if bun:
                kiji_list = kiji_list.filter(bunrui__id=bun)

            categ=request.GET.getlist("categ")
            if categ:
                moji = categ
                queries = [Q(category__id=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

            title = request.GET.get('title')
            if title:
                moji = title.split()
                queries = [Q(title__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

            author = request.GET.get('author')
            if author:
                moji = author.split()
                queries = [Q(author__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

            vol = request.GET.getlist('vol')
            if vol:
                moji = vol
                queries = [Q(volume=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

            n = request.GET.getlist('n')
            if n:
                moji = n
                queries = [Q(no=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

            word = request.GET.get('word')
            if word:
                moji = word.split()
                queries = [Q(keyword__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)

        return render(request, "list/ShowList1.html", {'kiji_list':kiji_list})

    else:
        form = SearchDetailForm()
        return render(request, "search/SearchDetail.html", {'form':form} )


def ShowListView3(request,id,shurui):

    #bunrui
    if shurui == 0:
        kiji_list=Kijis.objects.filter(bunrui__id=id)
    
    #author
    if shurui == 1:
        kiji_list=Kijis.objects.filter(author__id=id)

    #keyword
    if shurui == 2:
        kiji_list=Kijis.objects.filter(keyword__id=id)

    return render(request, "list/ShowList1.html", {'kiji_list':kiji_list})
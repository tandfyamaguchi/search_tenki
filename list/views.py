from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import logging
logger = logging.getLogger('development')

from .models import Kijis, Bunrui, Category, Author, Keyword 
from search.models import Year, Month
from search.forms import SearchDetailForm
from mysite import settings
PDF_URL='https://www.metsoc.jp/tenki/pdf/'

# ページネーション用に、Pageオブジェクトを返す。
def paginate_query(request, queryset):
  count=20
  queryset = queryset.order_by('id').reverse()
  paginator = Paginator(queryset, count)
  page = request.GET.get('page')
  try:
    page_obj = paginator.page(page)
  except PageNotAnInteger:
    page_obj = paginator.page(1)
  except EmptyPage:
    page_obj = paginatot.page(paginator.num_pages)
  return page_obj

#volとnoの一致するKijisを取得
def ShowListView1(request,id):
    search=Month.objects.filter(id=id)[0]
    vol=search.volume.volume
    n=search.no

    kiji_list=Kijis.objects.filter(volume=vol, no=n)
    page_obj = paginate_query(request, kiji_list)
    kensu = kiji_list.count()
    joken = '「卷:'+str(vol)+'」「号:'+str(n)+'」'

    context={'page_obj':page_obj, 'kensu':kensu, 'joken':joken, 'PDF_URL':PDF_URL}

    return render(request, "list/ShowList1.html", context)

#詳細検索の条件に一致するKijiを取得
def ShowListView2(request):
    
    if request.method == 'GET':
        kiji_list = Kijis.objects.all()
        joken=''

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
                n = Bunrui.objects.get(id=bun).name
                joken +=  '「内容分類:'+n+'」'

            categ=request.GET.getlist("categ")
            if categ:
                moji = categ
                queries = [Q(category__id=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                queries = [Q(id=m) for m in moji]
                query = make_query(queries)
                n = Category.objects.filter(query)
                joken += '「カテゴリー:'+'　'.join(m.name for m in n)+'」'

            title = request.GET.get('title')
            if title:
                moji = title.split()
                queries = [Q(title__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「タイトル:'+'　'.join(m for m in moji)+'」'

            author = request.GET.get('author')
            if author:
                moji = author.split()
                queries = [Q(author__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「著者名:'+'　'.join(m for m in moji)+'」'

            vol = request.GET.getlist('vol')
            if vol:
                moji = vol
                queries = [Q(volume=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「巻:'+'　'.join(str(m) for m in moji)+'」'

            n = request.GET.getlist('n')
            if n:
                moji = n
                queries = [Q(no=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「号:'+'　'.join(str(m) for m in moji)+'」'

            word = request.GET.get('word')
            if word:
                moji = word.split()
                queries = [Q(keyword__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「キーワード:'+'　'.join(m for m in moji)+'」'

        page_obj = paginate_query(request, kiji_list)
        kensu = kiji_list.count()
        context={'page_obj':page_obj, 'kensu':kensu, 'joken':joken, 'PDF_URL':PDF_URL}

        return render(request, "list/ShowList1.html", context)

    else:
        form = SearchDetailForm()
        return render(request, "search/SearchDetail.html", {'form':form} )


#検索結果からbunrui, author, keywordに一致するKijiを取得
def ShowListView3(request,id,shurui):
    #bunrui
    if shurui == 0:
        kiji_list=Kijis.objects.filter(bunrui__id=id)
        joken = '「内容分類:'+Bunrui.objects.get(id=id).name+'」'
    
    #author
    if shurui == 1:
        kiji_list=Kijis.objects.filter(author__id=id)
        joken = '「著者名:'+Author.objects.get(id=id).name+'」'

    #keyword
    if shurui == 2:
        kiji_list=Kijis.objects.filter(keyword__id=id)
        joken = '「キーワード:'+Keyword.objects.get(id=id).name+'」'

    page_obj = paginate_query(request, kiji_list)
    kensu = kiji_list.count()
    context={'page_obj':page_obj, 'kensu':kensu, 'joken':joken, 'PDF_URL':PDF_URL}

    return render(request, "list/ShowList1.html", context)
#検索に一致するKijiを取得
#ShowListView1:ShowListView1から検索条件取得
#ShowListView2:SearchDetail.htmlから検索条件取得
#ShowListView3:ShowList1.htmlから検索条件取得
from django.shortcuts import render
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import logging
logger = logging.getLogger('development')

from .models import Kijis, Bunrui, Category, Author, Keyword 
from search.models import Month
from search.forms import SearchDetailForm
from mysite import settings
PDF_URL='https://www.metsoc.jp/tenki/pdf/'

# ページネーション用に、Pageオブジェクトを返す。
def paginate_query(request, queryset, pages):
  count=pages
  queryset = queryset.order_by('id').reverse()
  paginator = Paginator(queryset, count)
  page = request.GET.get('page')
  try:
    page_obj = paginator.page(page)
  except PageNotAnInteger:
    page_obj = paginator.page(1)
  except EmptyPage:
    page_obj = paginator.page(paginator.num_pages)
  return page_obj

#volとnoの一致するKijisを取得
def ShowListView1(request,id):
    search=Month.objects.filter(id=id)[0]
    vol=search.volume.volume
    n=search.no

    kiji_list=Kijis.objects.filter(volume=vol, no=n)
    page_obj = paginate_query(request, kiji_list, 30)
    kensu = kiji_list.count()
    joken = '「巻:'+str(vol)+'」「号:'+str(n)+'」'

    context={'page_obj':page_obj, 'kensu':kensu, 'joken':joken, 'PDF_URL':PDF_URL}

    return render(request, "list/ShowList1.html", context)

#詳細検索の条件に一致するKijiを取得
def ShowListView2(request):
    
    if request.method == 'GET':
        kiji_list = Kijis.objects.all()
        #検索条件(htmlに表示するため)
        joken=''

        form = SearchDetailForm(request.GET)
        if form.is_valid():

            def make_query(queries):
                query = queries.pop()
                for item in queries:
                    query |= item
                return query

            #内容分類と一致する記事を抽出
            bun=request.GET.get("bun")
            if bun:
                kiji_list = kiji_list.filter(bunrui__id=bun)
                n = Bunrui.objects.get(id=bun).name
                joken +=  '「内容分類:'+n+'」'

            #カテゴリーと一致する記事を抽出
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

            #タイトルを含む記事を抽出
            title = request.GET.get('title')
            if title:
                moji = title.split()
                queries = [Q(title__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「タイトル:'+'　'.join(m for m in moji)+'」'

            #著者名を含む記事を抽出
            author = request.GET.get('author')
            if author:
                moji = author.split()
                queries = [Q(author__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「著者名:'+'　'.join(m for m in moji)+'」'

            #巻と一致する記事を抽出
            vol = request.GET.getlist('vol')
            if vol:
                moji = vol
                queries = [Q(volume=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「巻:'+'　'.join(str(m) for m in moji)+'」'

            #号と一致する記事を抽出
            n = request.GET.getlist('n')
            if n:
                moji = n
                queries = [Q(no=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「号:'+'　'.join(str(m) for m in moji)+'」'

            #キーワードを含む記事を抽出
            word = request.GET.get('word')
            if word:
                moji = word.split()
                queries = [Q(keyword__name__icontains=m) for m in moji]
                query = make_query(queries)
                kiji_list = kiji_list.filter(query)
                joken += '「キーワード:'+'　'.join(m for m in moji)+'」'

            order = request.GET.get('order')
            if order == "0":
                kiji_list = kiji_list.order_by('volume')
            elif order == "1":
                kiji_list = kiji_list.order_by('volume').reverse()

        #ページネーションに対応させる(request, 記事一覧, ページあたり表示件数)
        page_obj = paginate_query(request, kiji_list, request.GET.get('pages'))
        #検索結果件数
        kensu = kiji_list.count()
        #htmlへの引数(ページネーションに対応した記事一覧, 検索結果件数, 検索条件, PDFのURL)
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

    page_obj = paginate_query(request, kiji_list, 30)
    kensu = kiji_list.count()
    context={'page_obj':page_obj, 'kensu':kensu, 'joken':joken, 'PDF_URL':PDF_URL}

    return render(request, "list/ShowList1.html", context)

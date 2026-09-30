#検索に一致するKijiを取得
#ShowListView1:ShowListView1から検索条件取得
#ShowListView2:SearchDetail.htmlから検索条件取得
#ShowListView3:ShowList1.htmlから検索条件取得
from collections import defaultdict

from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Author, Bunrui, Kijis, Keyword
from search.models import Month
from search.forms import SearchDetailForm, parse_search_expression
from .sorting import (
  PUBLICATION_SORT_FIELD,
  apply_article_sort,
  order_articles_by_publication,
)

# ページネーション用に、Pageオブジェクトを返す。
def paginate_query(request, queryset, pages):
  if not queryset.ordered:
    queryset = queryset.order_by('id').reverse()
  paginator = Paginator(queryset, pages)
  page = request.GET.get('page')
  try:
    page_obj = paginator.page(page)
  except PageNotAnInteger:
    page_obj = paginator.page(1)
  except EmptyPage:
    page_obj = paginator.page(paginator.num_pages)
  return page_obj

# 巻・号を数値として扱い、巻、号、開始頁の刊行順で並べる。
def order_articles(queryset, order):
  direction = 'asc' if order == '1' else 'desc'
  return order_articles_by_publication(queryset, direction)

# 一覧表示に必要な関連データをまとめて取得する。
def with_article_relations(queryset):
  return queryset.select_related('category').prefetch_related(
    'bunrui', 'keyword'
  )

# Google風の検索式を、指定項目の記事一覧へ適用する。
def filter_by_search_expression(queryset, lookup, expression):
  positive_groups, excluded_terms = parse_search_expression(expression)
  positive_query = None
  article_manager = queryset.model._default_manager.using(queryset.db)

  # ORで区切られた各語群を、空白区切りのAND条件として作る。
  for terms in positive_groups:
    matching_articles = article_manager.all()
    for term in terms:
      # 多対多項目では、別々の関連レコードに一致するAND検索も可能にする。
      matching_articles = matching_articles.filter(**{lookup: term})

    group_query = Q(pk__in=matching_articles.values('pk'))
    if positive_query is None:
      positive_query = group_query
    else:
      positive_query |= group_query

  # 肯定語群がある場合だけ、ORでまとめた一致記事に絞り込む。
  if positive_query is not None:
    queryset = queryset.filter(positive_query)

  # 除外語は、すべてのOR候補に共通するNOT条件として適用する。
  for term in excluded_terms:
    queryset = queryset.exclude(**{lookup: term})

  return queryset

# 著者を中間テーブルへの登録順で各記事へ設定する。
def attach_ordered_authors(page_obj):
  article_queryset = page_obj.object_list
  database_alias = article_queryset.db
  articles = list(article_queryset)
  authors_by_article = defaultdict(list)
  article_ids = [article.id for article in articles]

  if article_ids:
    article_author = Kijis.author.through
    relations = (
      article_author.objects.using(database_alias)
      .filter(kijis_id__in=article_ids)
      .select_related('author')
      .order_by('id')
    )
    for relation in relations:
      authors_by_article[relation.kijis_id].append(relation.author)

  for article in articles:
    article.ordered_authors = authors_by_article[article.id]
  page_obj.object_list = articles


# 記事一覧に共通する関連取得、ページ分割、画面表示を行う。
def render_article_list(
    request,
    queryset,
    *,
    page_size,
    search_condition,
    sort_field,
    sort_direction,
):
    queryset = with_article_relations(queryset)
    page_obj = paginate_query(request, queryset, page_size)
    attach_ordered_authors(page_obj)
    context = {
        'page_obj': page_obj,
        'kensu': page_obj.paginator.count,
        'joken': search_condition,
        'PDF_URL': settings.PDF_URL,
        'sort_field': sort_field,
        'sort_direction': sort_direction,
    }
    return render(request, "list/ShowList1.html", context)


# 巻と号に一致する記事を取得する。
def ShowListView1(request,id):
    # 存在しない号IDは、IndexErrorではなく404として扱う。
    search = get_object_or_404(
        Month.objects.select_related('volume'),
        pk=id,
    )
    vol=search.volume.volume
    n=search.no

    kiji_list=Kijis.objects.filter(volume=vol, no=n)
    kiji_list, sort_field, sort_direction = apply_article_sort(
        kiji_list,
        request,
    )
    # 年度（巻）検索の初期表示は、刊行順の降順にする。
    if not sort_field:
        kiji_list = order_articles_by_publication(kiji_list, 'desc')
        sort_field = PUBLICATION_SORT_FIELD
        sort_direction = 'desc'
    joken = '「巻:'+str(vol)+'」「号:'+str(n)+'」'

    return render_article_list(
        request,
        kiji_list,
        page_size=30,
        search_condition=joken,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )

# 詳細検索の条件に一致する記事を取得する。
def ShowListView2(request):
    
    if request.method == 'GET':
        kiji_list = Kijis.objects.all()
        #検索条件(htmlに表示するため)
        joken=''

        form = SearchDetailForm(request.GET)
        
        #フォームが無効な場合は、入力画面を返す
        if not form.is_valid():
            return render(
                request,
                "search/SearchDetail.html",
                {'form': form},
                status=400,
            )

        cleaned = form.cleaned_data

        # 複数の検索条件をORでまとめる。
        def make_query(queries):
            query = queries.pop()
            for item in queries:
                query |= item
            return query

        #内容分類と一致する記事を抽出
        bun=cleaned["bun"]
        if bun:
            kiji_list = kiji_list.filter(bunrui=bun)
            joken +=  '「内容分類:'+bun.name+'」'

        #カテゴリーと一致する記事を抽出
        categ=list(cleaned["categ"])
        if categ:
            moji = [m.id for m in categ]
            queries = [Q(category__id=m) for m in moji]
            query = make_query(queries)
            kiji_list = kiji_list.filter(query)
            joken += '「カテゴリー:'+'　'.join(m.name for m in categ)+'」'

        #タイトルを含む記事を抽出
        title = cleaned['title']
        if title:
            kiji_list = filter_by_search_expression(
                kiji_list,
                'title__icontains',
                title,
            )
            joken += '「タイトル:'+title+'」'

        #著者名を含む記事を抽出
        author = cleaned['author']
        if author:
            kiji_list = filter_by_search_expression(
                kiji_list,
                'author__name__icontains',
                author,
            )
            joken += '「著者名:'+author+'」'

        #巻と一致する記事を抽出
        vol = cleaned['vol']
        if vol:
            moji = [str(m.volume) for m in vol]
            queries = [Q(volume=m) for m in moji]
            query = make_query(queries)
            kiji_list = kiji_list.filter(query)
            joken += '「巻:'+'　'.join(str(m) for m in moji)+'」'

        #号と一致する記事を抽出
        n = cleaned['n']
        if n:
            # 検証済みの整数を、記事DBの文字列型に合わせる。
            moji = [str(number) for number in n]
            queries = [Q(no=m) for m in moji]
            query = make_query(queries)
            kiji_list = kiji_list.filter(query)
            joken += '「号:'+'　'.join(moji)+'」'

        #キーワードを含む記事を抽出
        word = cleaned['word']
        if word:
            kiji_list = filter_by_search_expression(
                kiji_list,
                'keyword__name__icontains',
                word,
            )
            joken += '「キーワード:'+word+'」'

        # 多対多検索で重複した記事を1件にまとめる。
        kiji_list = kiji_list.distinct()
        kiji_list, sort_field, sort_direction = apply_article_sort(
            kiji_list,
            request,
        )
        # 見出しが未選択の場合は、詳細検索の並び順を使う。
        if not sort_field:
            kiji_list = order_articles(kiji_list, cleaned['order'])
            sort_field = PUBLICATION_SORT_FIELD
            sort_direction = (
                'asc' if cleaned['order'] == '1' else 'desc'
            )

        return render_article_list(
            request,
            kiji_list,
            page_size=cleaned['pages'],
            search_condition=joken,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )
    
    else:
        form = SearchDetailForm()
        return render(request, "search/SearchDetail.html", {'form':form} )


# 検索結果を内容分類、著者、キーワードで絞り込む。
def ShowListView3(request,id,shurui):
    #bunrui
    if shurui == 0:
        bunrui = get_object_or_404(Bunrui, pk=id)
        kiji_list=Kijis.objects.filter(bunrui__id=id)
        joken = '「内容分類:'+bunrui.name+'」'
    
    #author
    elif shurui == 1:
        author = get_object_or_404(Author, pk=id)
        kiji_list=Kijis.objects.filter(author__id=id)
        joken = '「著者名:'+author.name+'」'

    #keyword
    elif shurui == 2:
        keyword = get_object_or_404(Keyword, pk=id)
        kiji_list=Kijis.objects.filter(keyword__id=id)
        joken = '「キーワード:'+keyword.name+'」'
    else:
        # URLで許可していない関連項目種別は404として扱う。
        raise Http404('無効な関連項目の種類です。')

    kiji_list, sort_field, sort_direction = apply_article_sort(
        kiji_list,
        request,
    )

    return render_article_list(
        request,
        kiji_list,
        page_size=30,
        search_condition=joken,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )

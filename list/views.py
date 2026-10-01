# 検索条件に一致する記事を取得して一覧表示する。
from collections import defaultdict

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from search.forms import SearchDetailForm, parse_search_expression
from search.models import Month

from .models import Author, Bunrui, Kijis, Keyword
from .sorting import (
    PUBLICATION_SORT_FIELD,
    apply_article_sort,
    order_articles_by_publication,
)


# ページネーション用に、Pageオブジェクトを返す。
def paginate_query(request, queryset, page_size):
    if not queryset.ordered:
        queryset = queryset.order_by('-id')
    paginator = Paginator(queryset, page_size)
    return paginator.get_page(request.GET.get('page'))


# 巻・号を数値として扱い、巻、号、開始頁の刊行順で並べる。
def order_articles(queryset, sort_order):
    direction = 'asc' if sort_order == '1' else 'desc'
    return order_articles_by_publication(queryset, direction)


# 一覧表示に必要な関連データをまとめて取得する。
def with_article_relations(queryset):
    return queryset.select_related('category').prefetch_related(
        'bunrui',
        'keyword',
    )


# 検索方法を、指定項目の記事一覧へ適用する。
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


# 著者を指定された公開表示順で各記事へ設定する。
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
            .order_by('display_order', 'id')
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
        # 表示するページ番号をDjango標準の省略形式で渡す。
        'elided_page_range': list(
            page_obj.paginator.get_elided_page_range(page_obj.number)
        ),
        'page_ellipsis': page_obj.paginator.ELLIPSIS,
        'kensu': page_obj.paginator.count,
        'joken': search_condition,
        'PDF_URL': settings.PDF_URL,
        'sort_field': sort_field,
        'sort_direction': sort_direction,
    }
    return render(request, "list/ShowList1.html", context)


# 巻と号に一致する記事を取得する。
def ShowListView1(request, id):
    # 存在しない号IDは、IndexErrorではなく404として扱う。
    issue = get_object_or_404(
        Month.objects.select_related('volume'),
        pk=id,
    )
    volume_number = issue.volume.volume
    issue_number = issue.no

    articles = Kijis.objects.filter(volume=volume_number, no=issue_number)
    articles, sort_field, sort_direction = apply_article_sort(
        articles,
        request,
    )
    # 年度（巻）検索の初期表示は、刊行順の降順にする。
    if not sort_field:
        articles = order_articles_by_publication(articles, 'desc')
        sort_field = PUBLICATION_SORT_FIELD
        sort_direction = 'desc'
    search_condition = f'「巻:{volume_number}」「号:{issue_number}」'

    return render_article_list(
        request,
        articles,
        page_size=30,
        search_condition=search_condition,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )


# 詳細検索の条件に一致する記事を取得する。
def ShowListView2(request):
    if request.method != 'GET':
        return render(
            request,
            'search/SearchDetail.html',
            {'form': SearchDetailForm()},
        )

    articles = Kijis.objects.all()
    search_condition_parts = []
    form = SearchDetailForm(request.GET)

    # フォームが無効な場合は、入力画面を返す。
    if not form.is_valid():
        return render(
            request,
            'search/SearchDetail.html',
            {'form': form},
            status=400,
        )

    cleaned_data = form.cleaned_data

    # 内容分類と一致する記事を抽出する。
    bunrui = cleaned_data['bun']
    if bunrui:
        articles = articles.filter(bunrui=bunrui)
        search_condition_parts.append(f'「内容分類:{bunrui.name}」')

    # カテゴリと一致する記事を抽出する。
    categories = list(cleaned_data['categ'])
    if categories:
        category_ids = [category.id for category in categories]
        articles = articles.filter(category__id__in=category_ids)
        category_names = '　'.join(category.name for category in categories)
        search_condition_parts.append(f'「カテゴリー:{category_names}」')

    # タイトルを含む記事を抽出する。
    title = cleaned_data['title']
    if title:
        articles = filter_by_search_expression(
            articles,
            'title__icontains',
            title,
        )
        search_condition_parts.append(f'「タイトル:{title}」')

    # 著者名を含む記事を抽出する。
    author = cleaned_data['author']
    if author:
        articles = filter_by_search_expression(
            articles,
            'author__name__icontains',
            author,
        )
        search_condition_parts.append(f'「著者名:{author}」')

    # 巻と一致する記事を抽出する。
    volumes = cleaned_data['vol']
    if volumes:
        volume_numbers = [str(year.volume) for year in volumes]
        articles = articles.filter(volume__in=volume_numbers)
        volume_display = '　'.join(volume_numbers)
        search_condition_parts.append(f'「巻:{volume_display}」')

    # 号と一致する記事を抽出する。
    issue_numbers = cleaned_data['n']
    if issue_numbers:
        # 検証済みの整数を、記事DBの文字列型に合わせる。
        issue_numbers = [str(number) for number in issue_numbers]
        articles = articles.filter(no__in=issue_numbers)
        issue_display = '　'.join(issue_numbers)
        search_condition_parts.append(f'「号:{issue_display}」')

    # キーワードを含む記事を抽出する。
    keyword = cleaned_data['word']
    if keyword:
        articles = filter_by_search_expression(
            articles,
            'keyword__name__icontains',
            keyword,
        )
        search_condition_parts.append(f'「キーワード:{keyword}」')

    # 多対多検索で重複した記事を1件にまとめる。
    articles = articles.distinct()
    articles, sort_field, sort_direction = apply_article_sort(
        articles,
        request,
    )
    # 見出しが未選択の場合は、詳細検索の並び順を使う。
    if not sort_field:
        articles = order_articles(articles, cleaned_data['order'])
        sort_field = PUBLICATION_SORT_FIELD
        sort_direction = 'asc' if cleaned_data['order'] == '1' else 'desc'

    return render_article_list(
        request,
        articles,
        page_size=cleaned_data['pages'],
        search_condition=''.join(search_condition_parts),
        sort_field=sort_field,
        sort_direction=sort_direction,
    )


# 検索結果を内容分類、著者、キーワードで絞り込む。
def ShowListView3(request, id, shurui):
    # 内容分類で絞り込む。
    if shurui == 0:
        bunrui = get_object_or_404(Bunrui, pk=id)
        articles = Kijis.objects.filter(bunrui__id=id)
        search_condition = f'「内容分類:{bunrui.name}」'

    # 著者で絞り込む。
    elif shurui == 1:
        author = get_object_or_404(Author, pk=id)
        articles = Kijis.objects.filter(author__id=id)
        search_condition = f'「著者名:{author.name}」'

    # キーワードで絞り込む。
    elif shurui == 2:
        keyword = get_object_or_404(Keyword, pk=id)
        articles = Kijis.objects.filter(keyword__id=id)
        search_condition = f'「キーワード:{keyword.name}」'
    else:
        # URLで許可していない関連項目種別は404として扱う。
        raise Http404('無効な関連項目の種類です。')

    articles, sort_field, sort_direction = apply_article_sort(
        articles,
        request,
    )

    return render_article_list(
        request,
        articles,
        page_size=30,
        search_condition=search_condition,
        sort_field=sort_field,
        sort_direction=sort_direction,
    )

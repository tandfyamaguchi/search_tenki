# 検索結果一覧で使う並び替えURLを生成する。
from django import template

register = template.Library()

# 検索条件を保ち、指定した並び替えグループのURLを作る。
@register.simple_tag
def sort_url(request, target_sort, current_sort, current_direction):
    params = request.GET.copy()
    is_current_ascending = (
        current_sort == target_sort and current_direction == 'asc'
    )

    params['sort'] = target_sort
    params['direction'] = 'desc' if is_current_ascending else 'asc'
    params.pop('page', None)
    return params.urlencode()

import re
import unicodedata
from functools import lru_cache

from django.db import connections
from django.db.models import CharField, F, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Cast, Collate, Lower, NullIf, Trim

from .models import Kijis


ARTICLE_TEXT_COLLATION = 'article_text_order'
TEXT_SORT_FIELDS = {
    'category': 'category__name',
    'title': 'title',
}
PUBLICATION_SORT_FIELD = 'publication'
PUBLICATION_SORT_ALIASES = {'volume', 'no', 'startpage'}
SORTABLE_FIELDS = set(TEXT_SORT_FIELDS) | PUBLICATION_SORT_ALIASES | {
    'author', PUBLICATION_SORT_FIELD,
}
NATURAL_NUMBER_PATTERN = re.compile(r'([0-9]+)')


# カタカナを、比較用に対応するひらがなへ変換する。
def _katakana_to_hiragana(value):
    converted = []
    for character in value:
        code_point = ord(character)
        if 0x30A1 <= code_point <= 0x30F6:
            converted.append(chr(code_point - 0x60))
        elif 0x30FD <= code_point <= 0x30FE:
            converted.append(chr(code_point - 0x60))
        else:
            converted.append(character)
    return ''.join(converted)


# 文字列の先頭にある空白や記号を除き、比較対象の文字列を返す。
def _strip_leading_symbols(value):
    stripped = value.strip()
    if not stripped:
        return ''

    position = 0
    while position < len(stripped):
        category = unicodedata.category(stripped[position])
        if not stripped[position].isspace() and category[0] not in {'P', 'S'}:
            break
        position += 1

    # 記号だけの文字列は、空欄ではなく「その他」として扱う。
    return stripped[position:] or stripped


# 文字列を全半角・英字大小・ひらがな／カタカナの差を抑えて正規化する。
def _normalize_article_text(value):
    if value is None:
        return ''
    normalized = unicodedata.normalize('NFKC', str(value)).casefold()
    normalized = _katakana_to_hiragana(normalized)
    return _strip_leading_symbols(normalized)


# 先頭文字が日本語として扱う範囲に含まれるかを返す。
def _is_japanese_character(character):
    code_point = ord(character)
    return (
        0x3040 <= code_point <= 0x30FF
        or 0x3400 <= code_point <= 0x4DBF
        or 0x4E00 <= code_point <= 0x9FFF
        or 0xF900 <= code_point <= 0xFAFF
        or 0x20000 <= code_point <= 0x2FA1F
    )


# 数字部分を数値として比較できる、自然順のキーを作る。
def _natural_sort_parts(value):
    parts = []
    for part in NATURAL_NUMBER_PATTERN.split(value):
        if not part:
            continue
        if part.isdecimal():
            significant = part.lstrip('0') or '0'
            parts.append((0, int(significant), len(part)))
        else:
            parts.append((1, part))
    return tuple(parts)


# 日本語、英字、数字、その他、空欄の順になる比較キーを作る。
@lru_cache(maxsize=65536)
def _article_text_sort_key(value):
    normalized = _normalize_article_text(value)
    if not normalized:
        return (4, ())

    first_character = normalized[0]
    if _is_japanese_character(first_character):
        group = 0
    elif 'a' <= first_character <= 'z':
        group = 1
    elif '0' <= first_character <= '9':
        group = 2
    else:
        group = 3

    return (group, _natural_sort_parts(normalized))


# SQLiteの照合順として使用するため、2つの文字列を比較する。
def _compare_article_text(left, right):
    left_key = _article_text_sort_key(left)
    right_key = _article_text_sort_key(right)
    return (left_key > right_key) - (left_key < right_key)


# 現在のSQLite接続へ記事用の簡易文字列照合を登録する。
def _register_article_text_collation(database):
    if database.vendor != 'sqlite':
        return
    database.ensure_connection()
    database.connection.create_collation(
        ARTICLE_TEXT_COLLATION,
        _compare_article_text,
    )


# 空文字をNULLへ変換してから、文字列型の数値列を整数として扱う。
def numeric_text_expression(field_name):
    return Cast(
        NullIf(Trim(F(field_name)), Value('')),
        IntegerField(),
    )


# 昇順ではNULLを末尾、降順ではNULLを先頭にする並び順を返す。
def directional_order(expression, direction):
    if direction == 'desc':
        return expression.desc(nulls_first=True)
    return expression.asc(nulls_last=True)


# 巻、号、開始頁を、詳細検索と同じ刊行順でまとめて並べる。
def order_articles_by_publication(queryset, direction):
    return queryset.annotate(
        volume_number=numeric_text_expression('volume'),
        issue_number=numeric_text_expression('no'),
    ).order_by(
        directional_order(F('volume_number'), direction),
        directional_order(F('issue_number'), direction),
        directional_order(F('startpage'), direction),
        'id' if direction == 'asc' else '-id',
    )


# GETパラメータから、許可された列名と並び順だけを取得する。
def get_article_sort(request):
    sort_field = request.GET.get('sort', '')
    if sort_field not in SORTABLE_FIELDS:
        return '', 'asc'

    # 旧URLの列名も、巻・号・開始頁をまとめた刊行順として扱う。
    if sort_field in PUBLICATION_SORT_ALIASES:
        sort_field = PUBLICATION_SORT_FIELD

    direction = request.GET.get('direction', 'asc')
    if direction not in {'asc', 'desc'}:
        direction = 'asc'
    return sort_field, direction


# 指定された見出し列または刊行順で、記事全体を並べ替える。
def apply_article_sort(queryset, request):
    sort_field, direction = get_article_sort(request)
    if not sort_field:
        return queryset, sort_field, direction

    if sort_field == PUBLICATION_SORT_FIELD:
        return (
            order_articles_by_publication(queryset, direction),
            sort_field,
            direction,
        )

    database = connections[queryset.db]

    if sort_field in TEXT_SORT_FIELDS:
        source = F(TEXT_SORT_FIELDS[sort_field])
        if database.vendor == 'sqlite':
            _register_article_text_collation(database)
            source = Collate(source, ARTICLE_TEXT_COLLATION)
        else:
            source = Lower(source)
    else:
        article_author = Kijis.author.through
        first_author_name = (
            article_author.objects.using(queryset.db)
            .filter(kijis_id=OuterRef('pk'))
            # 公開時の先頭著者と同じ順で、著者列を並べ替える。
            .order_by('display_order', 'id')
            .values('author__name')[:1]
        )
        source = Subquery(first_author_name, output_field=CharField())
        if database.vendor == 'sqlite':
            _register_article_text_collation(database)
            source = Collate(source, ARTICLE_TEXT_COLLATION)
        else:
            source = Lower(source)
    # IDを第2キーにして、ページを移動しても文字列の表示順が揺れないようにする。
    return (
        queryset.order_by(directional_order(source, direction), 'id'),
        sort_field,
        direction,
    )

from collections import Counter

from django.core.management.base import CommandError

from ..models import Kiji, Naiyou
from list.models import Author, Bunrui, Category, Kijis, Keyword
from .common import (
    BATCH_SIZE,
    MAX_DISPLAY_VALUES,
    SOURCE_DATABASE,
    TARGET_DATABASE,
    format_limited_values,
)


# 旧DBの記事を検索用DBへ同期する処理をまとめる。
class LegacySynchronizer:
    preserve_legacy_relation_values = False

    # 初回投入後の検索用DBを、旧DBの内容へ同期する。
    def synchronize(self, preserve_legacy_relation_values=False):
        self.preserve_legacy_relation_values = preserve_legacy_relation_values
        prepared_data = self._prepare_synchronization()
        return self._synchronize(prepared_data)

    # 同期前に記事IDと参照データを検証し、同期用のデータを準備する。
    def _prepare_synchronization(self):
        source_articles = list(
            Kiji.objects.using(SOURCE_DATABASE).order_by('id').values(
                'id',
                'bunrui',
                'category',
                'title_jp',
                'author_jp',
                'volume',
                'start_page',
                'no',
                'keyword',
                'pdf',
            )
        )
        source_article_ids = {article['id'] for article in source_articles}
        target_articles_by_id = Kijis.objects.using(TARGET_DATABASE).in_bulk()
        self._validate_article_ids(
            source_article_ids,
            set(target_articles_by_id),
        )

        source_bunrui_by_id = dict(
            Naiyou.objects.using(SOURCE_DATABASE).order_by('id').values_list(
                'id',
                'title',
            )
        )
        target_bunrui_by_id = Bunrui.objects.using(TARGET_DATABASE).in_bulk()
        self._validate_bunrui_ids(
            set(source_bunrui_by_id),
            set(target_bunrui_by_id),
        )

        category_by_name = self._build_name_lookup(Category, 'カテゴリ')
        author_by_name = self._build_name_lookup(Author, '著者')
        keyword_by_name = self._build_name_lookup(Keyword, 'キーワード')
        (
            desired_relations,
            category_names,
            author_names,
            keyword_names,
            validation_errors,
        ) = self._prepare_desired_relations(
            source_articles,
            source_bunrui_by_id,
            target_bunrui_by_id,
        )
        self._raise_validation_errors(validation_errors)
        self._validate_category_names(category_names, category_by_name)

        return {
            'source_articles': source_articles,
            'target_articles_by_id': target_articles_by_id,
            'source_bunrui_by_id': source_bunrui_by_id,
            'target_bunrui_by_id': target_bunrui_by_id,
            'category_by_name': category_by_name,
            'author_by_name': author_by_name,
            'keyword_by_name': keyword_by_name,
            'desired_relations': desired_relations,
            'author_names': author_names,
            'keyword_names': keyword_names,
        }

    # 旧DBと検索用DBの記事IDが完全一致していることを確認する。
    def _validate_article_ids(self, source_ids, target_ids):
        self._validate_matching_ids(source_ids, target_ids, '記事ID')

    # 旧DBと検索用DBの内容分類IDが完全一致していることを確認する。
    def _validate_bunrui_ids(self, source_ids, target_ids):
        self._validate_matching_ids(source_ids, target_ids, '内容分類ID')

    # 2つのID集合が一致しない場合に、差分を示して中断する。
    def _validate_matching_ids(self, source_ids, target_ids, label):
        source_only = sorted(source_ids - target_ids)
        target_only = sorted(target_ids - source_ids)
        if source_only or target_only:
            raise CommandError(
                f'{label}が一致しません。'
                f'旧DBのみ: {format_limited_values(source_only)}; '
                f'検索用DBのみ: {format_limited_values(target_only)}'
            )

    # 対象モデルの名称が一意であることを確認して辞書にまとめる。
    def _build_name_lookup(self, model, label):
        objects_by_name = {}
        duplicate_names = []
        for obj in model.objects.using(TARGET_DATABASE).only('id', 'name').iterator():
            if obj.name in objects_by_name:
                duplicate_names.append(obj.name)
                continue
            objects_by_name[obj.name] = obj

        if duplicate_names:
            raise CommandError(
                f'{label}名が重複しています: '
                f'{format_limited_values(sorted(set(duplicate_names)))}'
            )
        return objects_by_name

    # 原稿種別を持つ承認済みカテゴリだけを初回同期で使用する。
    def _validate_category_names(self, source_category_names, category_by_name):
        missing_names = sorted(set(source_category_names) - set(category_by_name))
        if not missing_names:
            return

        raise CommandError(
            '旧DBにあるカテゴリが検索用DBへ未登録です。'
            '初回同期の前に、承認済みベースDBへ原稿種別付きで登録してください: '
            f'{format_limited_values(missing_names)}'
        )

    # 旧DBの記事から、同期後に必要となる関連データを検証して作成する。
    def _prepare_desired_relations(
        self,
        source_articles,
        source_bunrui_by_id,
        target_bunrui_by_id,
    ):
        desired_relations = {}
        category_names = set()
        author_names = set()
        keyword_names = set()
        validation_errors = []

        for article in source_articles:
            article_id = article['id']
            category_name = self._category_name(article['category'])
            if category_name:
                category_names.add(category_name)

            bunrui_values, bunrui_errors = self._parse_relation_values(
                article_id,
                '内容分類',
                article['bunrui'],
                ',',
            )
            author_values, author_errors = self._parse_relation_values(
                article_id,
                '著者',
                article['author_jp'],
                '・',
            )
            keyword_values, keyword_errors = self._parse_relation_values(
                article_id,
                'キーワード',
                article['keyword'],
                '、',
            )
            validation_errors.extend(bunrui_errors + author_errors + keyword_errors)

            bunrui_ids = set()
            if not bunrui_errors:
                for value in bunrui_values:
                    try:
                        bunrui_id = int(value)
                    except ValueError:
                        validation_errors.append(
                            f'記事ID {article_id} の内容分類ID「{value}」は整数ではありません。'
                        )
                        continue
                    if (
                        bunrui_id not in source_bunrui_by_id
                        or bunrui_id not in target_bunrui_by_id
                    ):
                        validation_errors.append(
                            f'記事ID {article_id} の内容分類ID「{value}」は参照できません。'
                        )
                        continue
                    if bunrui_id in bunrui_ids:
                        validation_errors.append(
                            f'記事ID {article_id} の内容分類ID「{value}」は重複しています。'
                        )
                        continue
                    bunrui_ids.add(bunrui_id)

            if not author_errors:
                author_names.update(author_values)
            if not keyword_errors:
                keyword_names.update(keyword_values)
            desired_relations[article_id] = {
                'bunrui': bunrui_ids,
                'author_names': tuple(author_values) if not author_errors else (),
                'keyword_names': set(keyword_values) if not keyword_errors else set(),
            }

        return (
            desired_relations,
            category_names,
            author_names,
            keyword_names,
            validation_errors,
        )

    # 区切り文字を含む関連データを分解し、空値・空白・重複を検証する。
    def _parse_relation_values(self, article_id, field_name, raw_value, separator):
        if raw_value is None or raw_value == '':
            return (), []

        values = tuple(raw_value.split(separator))
        if self.preserve_legacy_relation_values:
            # 初回移行では、旧DBに記録された表記を変更せずに引き継ぐ。
            return values, []

        errors = []
        for value in values:
            if not value.strip():
                errors.append(
                    f'記事ID {article_id} の{field_name}に空の値があります。'
                )
            elif value != value.strip():
                errors.append(
                    f'記事ID {article_id} の{field_name}「{value}」の前後に空白があります。'
                )

        duplicate_values = {
            value
            for value, count in Counter(values).items()
            if count > 1 and value.strip()
        }
        if duplicate_values:
            errors.append(
                f'記事ID {article_id} の{field_name}に重複があります: '
                f'{", ".join(sorted(duplicate_values))}'
            )
        return values, errors

    # カテゴリの空文字を未分類として扱う。
    def _category_name(self, category_name):
        if category_name is None or not category_name.strip():
            return None
        return category_name

    # 旧DBの検証エラーをまとめて表示し、書き込み前に中断する。
    def _raise_validation_errors(self, validation_errors):
        if not validation_errors:
            return

        displayed_errors = validation_errors[:MAX_DISPLAY_VALUES]
        message = '\n'.join(displayed_errors)
        remaining_count = len(validation_errors) - MAX_DISPLAY_VALUES
        if remaining_count > 0:
            message += f'\nほか{remaining_count}件の検証エラーがあります。'
        raise CommandError(f'旧DBのデータを検証できません。\n{message}')

    # 準備済みのデータを使い、記事本体と関連データを差分同期する。
    def _synchronize(self, prepared_data):
        # カテゴリは原稿種別を持つ承認済みベースDBからだけ参照する。
        statistics = {
            'categories_created': 0,
            'authors_created': 0,
            'keywords_created': 0,
        }
        statistics['articles_updated'] = self._synchronize_articles(prepared_data)
        statistics['bunrui_updated'] = self._synchronize_bunrui_names(prepared_data)
        statistics['authors_created'] = self._ensure_named_records(
            Author,
            '著者',
            prepared_data['author_names'],
            prepared_data['author_by_name'],
        )
        statistics['keywords_created'] = self._ensure_named_records(
            Keyword,
            'キーワード',
            prepared_data['keyword_names'],
            prepared_data['keyword_by_name'],
        )

        desired_pairs = self._build_desired_pairs(prepared_data)
        relation_specs = (
            ('bunrui', Kijis.bunrui.through, 'bunrui_id'),
            ('keyword', Kijis.keyword.through, 'keyword_id'),
        )
        for relation_name, through_model, related_field_name in relation_specs:
            result = self._synchronize_relation(
                through_model,
                related_field_name,
                desired_pairs[relation_name],
            )
            statistics[f'{relation_name}_created'] = result['created']
            statistics[f'{relation_name}_deleted'] = result['deleted']
        author_result = self._synchronize_ordered_author_relations(
            desired_pairs['author_by_article'],
        )
        statistics['author_created'] = author_result['created']
        statistics['author_deleted'] = author_result['deleted']
        return statistics

    # 旧DBの記事本体の項目を検索用DBの同じIDの記事へ反映する。
    def _synchronize_articles(self, prepared_data):
        articles_to_update = []
        for source_article in prepared_data['source_articles']:
            target_article = prepared_data['target_articles_by_id'][source_article['id']]
            category_name = self._category_name(source_article['category'])
            category_id = (
                prepared_data['category_by_name'][category_name].id
                if category_name
                else None
            )
            values = {
                'title': source_article['title_jp'],
                'volume': self._text_value(source_article['volume']),
                'startpage': source_article['start_page'],
                'no': self._text_value(source_article['no']),
                'pdf': source_article['pdf'],
            }
            is_changed = False
            for field_name, value in values.items():
                if getattr(target_article, field_name) != value:
                    setattr(target_article, field_name, value)
                    is_changed = True
            if target_article.category_id != category_id:
                target_article.category_id = category_id
                is_changed = True
            if is_changed:
                articles_to_update.append(target_article)

        if articles_to_update:
            Kijis.objects.using(TARGET_DATABASE).bulk_update(
                articles_to_update,
                ['title', 'volume', 'startpage', 'no', 'pdf', 'category'],
                batch_size=BATCH_SIZE,
            )
        return len(articles_to_update)

    # 数値型の巻・号を検索用DBの文字列型へ変換する。
    def _text_value(self, value):
        return str(value) if value is not None else None

    # 旧DBの内容分類名称を検索用DBの同じIDの内容分類へ反映する。
    def _synchronize_bunrui_names(self, prepared_data):
        bunrui_to_update = []
        for bunrui_id, source_name in prepared_data['source_bunrui_by_id'].items():
            target_bunrui = prepared_data['target_bunrui_by_id'][bunrui_id]
            if target_bunrui.name != source_name:
                target_bunrui.name = source_name
                bunrui_to_update.append(target_bunrui)

        if bunrui_to_update:
            Bunrui.objects.using(TARGET_DATABASE).bulk_update(
                bunrui_to_update,
                ['name'],
                batch_size=BATCH_SIZE,
            )
        return len(bunrui_to_update)

    # 未登録の著者またはキーワードをまとめて登録し、名称辞書を更新する。
    def _ensure_named_records(self, model, label, names, objects_by_name):
        missing_names = sorted(set(names) - set(objects_by_name))
        if not missing_names:
            return 0

        model.objects.using(TARGET_DATABASE).bulk_create(
            [model(name=name) for name in missing_names],
            batch_size=BATCH_SIZE,
        )
        objects_by_name.update(self._build_name_lookup(model, label))
        return len(missing_names)

    # 名称と内容分類IDから、同期後に必要な記事関連と著者順を作る。
    def _build_desired_pairs(self, prepared_data):
        desired_pairs = {
            'bunrui': set(),
            'keyword': set(),
            'author_by_article': {},
        }
        for article_id, relations in prepared_data['desired_relations'].items():
            desired_pairs['bunrui'].update(
                (article_id, bunrui_id) for bunrui_id in relations['bunrui']
            )
            desired_pairs['author_by_article'][article_id] = tuple(
                prepared_data['author_by_name'][author_name].id
                for author_name in relations['author_names']
            )
            desired_pairs['keyword'].update(
                (article_id, prepared_data['keyword_by_name'][keyword_name].id)
                for keyword_name in relations['keyword_names']
        )
        return desired_pairs

    # 著者の多対多関連と公開表示順を、旧DBの記載順に合わせて差分同期する。
    def _synchronize_ordered_author_relations(self, desired_author_ids_by_article):
        through_model = Kijis.author.through
        existing_rows_by_article = {}
        for relation_id, article_id, author_id, display_order in through_model.objects.using(
            TARGET_DATABASE
        ).order_by('kijis_id', 'display_order', 'id').values_list(
            'id',
            'kijis_id',
            'author_id',
            'display_order',
        ):
            existing_rows_by_article.setdefault(article_id, []).append(
                (relation_id, author_id, display_order)
            )

        relation_ids_to_delete = []
        rows_to_create = []
        for article_id in sorted(desired_author_ids_by_article):
            existing_rows = existing_rows_by_article.get(article_id, [])
            existing_author_ids = tuple(
                author_id for _id, author_id, _display_order in existing_rows
            )
            existing_display_orders = tuple(
                display_order for _id, _author_id, display_order in existing_rows
            )
            desired_author_ids = desired_author_ids_by_article[article_id]
            desired_display_orders = tuple(
                range(1, len(desired_author_ids) + 1)
            )
            if (
                existing_author_ids == desired_author_ids
                and existing_display_orders == desired_display_orders
            ):
                continue

            relation_ids_to_delete.extend(
                relation_id
                for relation_id, _author_id, _display_order in existing_rows
            )
            rows_to_create.extend(
                through_model(
                    kijis_id=article_id,
                    author_id=author_id,
                    display_order=display_order,
                )
                for display_order, author_id in enumerate(desired_author_ids, start=1)
            )

        for relation_ids in self._chunked(relation_ids_to_delete):
            through_model.objects.using(TARGET_DATABASE).filter(
                id__in=relation_ids
            ).delete()
        if rows_to_create:
            through_model.objects.using(TARGET_DATABASE).bulk_create(
                rows_to_create,
                batch_size=BATCH_SIZE,
            )
        return {'created': len(rows_to_create), 'deleted': len(relation_ids_to_delete)}

    # 既存の多対多関連を、必要な組合せとの差分だけ追加・削除する。
    def _synchronize_relation(self, through_model, related_field_name, desired_pairs):
        existing_rows_by_pair = {
            (article_id, related_id): relation_id
            for relation_id, article_id, related_id in through_model.objects.using(
                TARGET_DATABASE
            ).values_list('id', 'kijis_id', related_field_name)
        }
        existing_pairs = set(existing_rows_by_pair)
        pairs_to_delete = existing_pairs - desired_pairs
        pairs_to_create = desired_pairs - existing_pairs

        relation_ids_to_delete = [
            existing_rows_by_pair[pair] for pair in pairs_to_delete
        ]
        for relation_ids in self._chunked(relation_ids_to_delete):
            through_model.objects.using(TARGET_DATABASE).filter(
                id__in=relation_ids
            ).delete()

        rows_to_create = [
            through_model(
                kijis_id=article_id,
                **{related_field_name: related_id},
            )
            for article_id, related_id in sorted(pairs_to_create)
        ]
        if rows_to_create:
            through_model.objects.using(TARGET_DATABASE).bulk_create(
                rows_to_create,
                batch_size=BATCH_SIZE,
            )
        return {'created': len(rows_to_create), 'deleted': len(relation_ids_to_delete)}

    # SQLiteのパラメータ上限を超えない大きさで一覧を分割する。
    def _chunked(self, values):
        for start in range(0, len(values), BATCH_SIZE):
            yield values[start:start + BATCH_SIZE]

    # 同期結果を作成・更新・削除件数として整形する。
    @staticmethod
    def format_summary(statistics):
        return (
            f"記事更新: {statistics['articles_updated']}件、"
            f"内容分類名更新: {statistics['bunrui_updated']}件、"
            f"カテゴリ新規: {statistics['categories_created']}件、"
            f"著者新規: {statistics['authors_created']}件、"
            f"キーワード新規: {statistics['keywords_created']}件、"
            f"分類関連 追加/削除: {statistics['bunrui_created']}/"
            f"{statistics['bunrui_deleted']}件、"
            f"著者関連 追加/削除: {statistics['author_created']}/"
            f"{statistics['author_deleted']}件、"
            f"キーワード関連 追加/削除: {statistics['keyword_created']}/"
            f"{statistics['keyword_deleted']}件"
        )

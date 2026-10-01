import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from basemodel.models import Kiji, Naiyou
from basemodel.services.legacy_sync import LegacySynchronizer
from list.models import (
    ArticleAuthor,
    Author,
    Bunrui,
    Category,
    CategoryGroup,
    Kijis,
    Keyword,
)
from search.models import Month, Year


SOURCE_DATABASE = 'etenki'
TARGET_DATABASE = 'default'
BATCH_SIZE = 500
INITIAL_DATA_DIRECTORY = Path(__file__).resolve().parents[2] / 'initial_data'


# 空の検索用DBを初回データで構成し、旧DBとの同期まで実行する。
class Command(BaseCommand):
    help = '空の検索用DBへ初回データを投入し、旧DBの内容を同期する。'

    # 誤操作を避けるため、検証か実行かを明示的に選ばせる。
    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            '--dry-run',
            action='store_true',
            help='初期投入と同期を検証し、検索用DBへの変更をロールバックする。',
        )
        mode.add_argument(
            '--apply',
            action='store_true',
            help='初期投入と同期を確定する。空の検索用DBに対して一度だけ実行する。',
        )

    # 指定されたモードで、初期投入と旧DB同期をまとめて実行する。
    def handle(self, *args, **options):
        if args:
            raise CommandError('このコマンドは位置引数を受け付けません。')

        initial_data = self._load_initial_data()
        source_data = self._load_source_data(initial_data['category_names'])
        is_dry_run = options['dry_run']

        # 初期投入と同期を一つのトランザクションとして扱う。
        with transaction.atomic(using=TARGET_DATABASE):
            self._validate_migrations()
            category_groups_by_key = self._validate_category_groups(
                initial_data['category_group_definitions'],
            )
            self._validate_target_is_empty()
            seed_counts = self._seed_target_data(
                initial_data,
                source_data,
                category_groups_by_key,
            )

            # 初回投入済みのIDを使って、旧DBの記事と関連データを同期する。
            synchronizer = LegacySynchronizer()
            synchronization_statistics = synchronizer.synchronize(
                preserve_legacy_relation_values=True,
            )

            if is_dry_run:
                transaction.set_rollback(True, using=TARGET_DATABASE)

        summary = self._format_summary(seed_counts, synchronization_statistics)
        if is_dry_run:
            return f'初回投入の検証が完了しました。DBへの変更はロールバックしました。{summary}'
        return f'初回投入と旧DB同期が完了しました。{summary}'

    # 初回投入用CSVとカテゴリの原稿種別対応を読み込む。
    def _load_initial_data(self):
        category_group_definitions = self._load_category_group_definitions()
        category_rows = self._load_category_rows()
        year_rows = self._load_year_rows()
        month_rows = self._load_month_rows()

        defined_group_keys = {
            group_key
            for group_key, _group_name, _display_order
            in category_group_definitions
        }
        referenced_group_keys = {
            group_key for _category_id, _name, group_key in category_rows
        }
        unknown_group_keys = sorted(referenced_group_keys - defined_group_keys)
        if unknown_group_keys:
            raise CommandError(
                'categories.csvが未定義の原稿種別キーを参照しています: '
                f'{self._format_values(unknown_group_keys)}'
            )

        year_ids = {year_id for year_id, _year, _volume in year_rows}
        referenced_year_ids = {
            volume_id
            for _month_id, volume_id, _start_page, _number in month_rows
        }
        missing_year_ids = sorted(referenced_year_ids - year_ids)
        if missing_year_ids:
            raise CommandError(
                'months.csvが参照する巻IDがyears.csvにありません: '
                f'{self._format_values(missing_year_ids)}'
            )

        return {
            'category_group_definitions': category_group_definitions,
            'category_rows': category_rows,
            'category_names': {
                name for _category_id, name, _group_key in category_rows
            },
            'year_rows': year_rows,
            'month_rows': month_rows,
        }

    # 原稿種別キー、名称、表示順の初期データを読み込む。
    def _load_category_group_definitions(self):
        filename = 'category_groups.csv'
        rows = []
        for line_number, row in self._read_csv_rows(filename, 3):
            group_key, group_name, raw_display_order = row
            if not group_key.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目の原稿種別キーが空です。'
                )
            if group_key != group_key.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目の原稿種別キーの前後に空白があります。'
                )
            if not group_name.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目の原稿種別名が空です。'
                )
            rows.append(
                (
                    group_key,
                    group_name,
                    self._parse_positive_integer(
                        raw_display_order,
                        '表示順',
                        filename,
                        line_number,
                    ),
                )
            )

        self._validate_unique_values(
            [group_key for group_key, _name, _display_order in rows],
            f'{filename}の原稿種別キー',
        )
        self._validate_unique_values(
            [name for _group_key, name, _display_order in rows],
            f'{filename}の原稿種別名',
        )
        self._validate_unique_values(
            [display_order for _group_key, _name, display_order in rows],
            f'{filename}の表示順',
        )
        return tuple(rows)

    # カテゴリID、名称、原稿種別キーの初期データを読み込む。
    def _load_category_rows(self):
        filename = 'categories.csv'
        rows = []
        for line_number, row in self._read_csv_rows(filename, 3):
            category_id = self._parse_positive_integer(
                row[0],
                'カテゴリID',
                filename,
                line_number,
            )
            category_name = row[1]
            group_key = row[2]
            if not category_name.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目のカテゴリ名が空です。'
                )
            if not group_key.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目の原稿種別キーが空です。'
                )
            if group_key != group_key.strip():
                raise CommandError(
                    f'{filename}の{line_number}行目の原稿種別キーの前後に空白があります。'
                )
            rows.append((category_id, category_name, group_key))

        self._validate_unique_values(
            [category_id for category_id, _name, _group_key in rows],
            f'{filename}のカテゴリID',
        )
        self._validate_unique_values(
            [name for _category_id, name, _group_key in rows],
            f'{filename}のカテゴリ名',
        )
        return tuple(rows)

    # 巻の初期データを読み込み、IDと巻番号の重複を検証する。
    def _load_year_rows(self):
        filename = 'years.csv'
        rows = []
        for line_number, row in self._read_csv_rows(filename, 3):
            rows.append(
                (
                    self._parse_positive_integer(
                        row[0], '巻ID', filename, line_number,
                    ),
                    self._parse_positive_integer(
                        row[1], '発行年', filename, line_number,
                    ),
                    self._parse_positive_integer(
                        row[2], '巻番号', filename, line_number,
                    ),
                )
            )

        self._validate_unique_values(
            [year_id for year_id, _year, _volume in rows],
            f'{filename}の巻ID',
        )
        self._validate_unique_values(
            [volume for _year_id, _year, volume in rows],
            f'{filename}の巻番号',
        )
        return tuple(rows)

    # 号の初期データを読み込み、巻と号の組合せを検証する。
    def _load_month_rows(self):
        filename = 'months.csv'
        rows = []
        for line_number, row in self._read_csv_rows(filename, 4):
            rows.append(
                (
                    self._parse_positive_integer(
                        row[0], '号ID', filename, line_number,
                    ),
                    self._parse_positive_integer(
                        row[1], '巻ID', filename, line_number,
                    ),
                    self._parse_nonnegative_integer(
                        row[2], '開始頁', filename, line_number,
                    ),
                    self._parse_positive_integer(
                        row[3], '号番号', filename, line_number,
                    ),
                )
            )

        self._validate_unique_values(
            [month_id for month_id, _volume_id, _start_page, _number in rows],
            f'{filename}の号ID',
        )
        self._validate_unique_values(
            [
                (volume_id, number)
                for _month_id, volume_id, _start_page, number in rows
            ],
            f'{filename}の巻・号',
        )
        return tuple(rows)

    # CSVをUTF-8として読み込み、列数を検証する。
    def _read_csv_rows(self, filename, expected_column_count):
        path = INITIAL_DATA_DIRECTORY / filename
        try:
            with path.open(encoding='utf-8-sig', newline='') as csv_file:
                rows = list(csv.reader(csv_file))
        except (OSError, UnicodeError, csv.Error) as error:
            raise CommandError(f'{filename}を読み込めません: {error}') from error

        if not rows:
            raise CommandError(f'{filename}が空です。')

        numbered_rows = []
        for line_number, row in enumerate(rows, start=1):
            if len(row) != expected_column_count:
                raise CommandError(
                    f'{filename}の{line_number}行目は{expected_column_count}列である必要があります。'
                )
            numbered_rows.append((line_number, row))
        return numbered_rows

    # 数値列を正の整数として読み取る。
    def _parse_positive_integer(self, raw_value, label, filename, line_number):
        try:
            value = int(raw_value)
        except ValueError as error:
            raise CommandError(
                f'{filename}の{line_number}行目の{label}「{raw_value}」は整数ではありません。'
            ) from error
        if value <= 0:
            raise CommandError(
                f'{filename}の{line_number}行目の{label}は1以上である必要があります。'
            )
        return value

    # 開始頁を0以上の整数として読み取る。
    def _parse_nonnegative_integer(self, raw_value, label, filename, line_number):
        try:
            value = int(raw_value)
        except ValueError as error:
            raise CommandError(
                f'{filename}の{line_number}行目の{label}「{raw_value}」は整数ではありません。'
            ) from error
        if value < 0:
            raise CommandError(
                f'{filename}の{line_number}行目の{label}は0以上である必要があります。'
            )
        return value

    # 旧DBの初期投入に必要な記事IDと内容分類IDを読み込む。
    def _load_source_data(self, available_category_names):
        try:
            article_rows = list(
                Kiji.objects.using(SOURCE_DATABASE).order_by('id').values_list(
                    'id',
                    'category',
                )
            )
            bunrui_rows = list(
                Naiyou.objects.using(SOURCE_DATABASE).order_by('id').values_list(
                    'id',
                    'title',
                )
            )
        except OperationalError as error:
            raise CommandError(
                'etenki.dbを読み込めません。配置と読み取り権限を確認してください。'
            ) from error

        if not article_rows:
            raise CommandError('etenki.dbに記事データがありません。')
        if not bunrui_rows:
            raise CommandError('etenki.dbに内容分類データがありません。')

        source_category_names = {
            category_name
            for _article_id, category_name in article_rows
            if category_name is not None and category_name.strip()
        }
        missing_category_names = sorted(source_category_names - available_category_names)
        if missing_category_names:
            raise CommandError(
                'etenki.dbにあるカテゴリがcategories.csvへ未登録です: '
                f'{self._format_values(missing_category_names)}'
            )

        return {
            'article_ids': tuple(
                article_id for article_id, _category_name in article_rows
            ),
            'bunrui_rows': tuple(bunrui_rows),
        }

    # 初期投入前に、defaultの全migrationが適用済みであることを確認する。
    def _validate_migrations(self):
        connection = connections[TARGET_DATABASE]
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            pending_migrations = [
                f'{migration.app_label}.{migration.name}'
                for migration, _backwards in plan
            ]
            raise CommandError(
                '初期投入の前に、defaultへmigrationを最後まで適用してください: '
                f'{self._format_values(pending_migrations)}'
            )

    # migrationで作成される原稿種別が、初期データと一致するか確認する。
    def _validate_category_groups(self, definitions):
        try:
            groups_by_name = {
                group.name: group
                for group in CategoryGroup.objects.using(TARGET_DATABASE).iterator()
            }
        except OperationalError as error:
            raise CommandError(
                '初期投入の前に、defaultへmigrationを最後まで適用してください。'
            ) from error

        expected_group_names = {
            group_name for _group_key, group_name, _display_order in definitions
        }
        actual_group_names = set(groups_by_name)
        if actual_group_names != expected_group_names:
            missing_names = sorted(expected_group_names - actual_group_names)
            unexpected_names = sorted(actual_group_names - expected_group_names)
            raise CommandError(
                '原稿種別の初期状態が一致しません。'
                f'不足: {self._format_values(missing_names)}; '
                f'想定外: {self._format_values(unexpected_names)}'
            )

        groups_by_key = {}
        for group_key, group_name, display_order in definitions:
            category_group = groups_by_name[group_name]
            if category_group.display_order != display_order:
                raise CommandError(
                    f'原稿種別「{group_name}」の表示順が初期値と一致しません。'
                )
            groups_by_key[group_key] = category_group
        return groups_by_key

    # 初期投入の対象テーブルに既存データがないことを確認する。
    def _validate_target_is_empty(self):
        target_models = (
            ('記事', Kijis),
            ('内容分類', Bunrui),
            ('カテゴリ', Category),
            ('著者', Author),
            ('キーワード', Keyword),
            ('巻', Year),
            ('号', Month),
            ('記事と内容分類の関連', Kijis.bunrui.through),
            ('記事と著者の関連', ArticleAuthor),
            ('記事とキーワードの関連', Kijis.keyword.through),
        )
        occupied_labels = [
            label
            for label, model in target_models
            if model.objects.using(TARGET_DATABASE).exists()
        ]
        if occupied_labels:
            raise CommandError(
                '初回投入の対象に既存データがあります。空のdb.sqlite3を用意してください: '
                f'{self._format_values(occupied_labels)}'
            )

    # CSVと旧DBから、IDを維持した初期レコードを作成する。
    def _seed_target_data(self, initial_data, source_data, category_groups_by_key):
        Kijis.objects.using(TARGET_DATABASE).bulk_create(
            [Kijis(id=article_id) for article_id in source_data['article_ids']],
            batch_size=BATCH_SIZE,
        )
        Bunrui.objects.using(TARGET_DATABASE).bulk_create(
            [
                Bunrui(id=bunrui_id, name=name)
                for bunrui_id, name in source_data['bunrui_rows']
            ],
            batch_size=BATCH_SIZE,
        )
        Category.objects.using(TARGET_DATABASE).bulk_create(
            [
                Category(
                    id=category_id,
                    name=name,
                    group_id=category_groups_by_key[group_key].id,
                )
                for category_id, name, group_key in initial_data['category_rows']
            ],
            batch_size=BATCH_SIZE,
        )
        Year.objects.using(TARGET_DATABASE).bulk_create(
            [
                Year(id=year_id, year=year, volume=volume)
                for year_id, year, volume in initial_data['year_rows']
            ],
            batch_size=BATCH_SIZE,
        )
        Month.objects.using(TARGET_DATABASE).bulk_create(
            [
                Month(
                    id=month_id,
                    volume_id=volume_id,
                    start_page=start_page,
                    no=number,
                )
                for month_id, volume_id, start_page, number
                in initial_data['month_rows']
            ],
            batch_size=BATCH_SIZE,
        )
        return {
            'articles': len(source_data['article_ids']),
            'bunrui': len(source_data['bunrui_rows']),
            'categories': len(initial_data['category_rows']),
            'years': len(initial_data['year_rows']),
            'months': len(initial_data['month_rows']),
        }

    # 初期投入件数と同期結果を表示用の文章へ整形する。
    def _format_summary(self, seed_counts, synchronization_statistics):
        synchronization_summary = LegacySynchronizer().format_summary(
            synchronization_statistics,
        )
        return (
            f" 初期投入: 記事ID {seed_counts['articles']}件、"
            f"内容分類ID {seed_counts['bunrui']}件、"
            f"カテゴリ {seed_counts['categories']}件、"
            f"巻 {seed_counts['years']}件、号 {seed_counts['months']}件。"
            f' 旧DB同期: {synchronization_summary}'
        )

    # 重複値があれば、初期データの不整合として中断する。
    def _validate_unique_values(self, values, label):
        duplicate_values = sorted(
            {value for value in values if values.count(value) > 1},
            key=str,
        )
        if duplicate_values:
            raise CommandError(
                f'{label}が重複しています: {self._format_values(duplicate_values)}'
            )

    # エラー表示用に値の一覧を短縮する。
    def _format_values(self, values):
        if not values:
            return 'なし'
        displayed_values = ', '.join(str(value) for value in values[:20])
        remaining_count = len(values) - 20
        if remaining_count > 0:
            return f'{displayed_values} ほか{remaining_count}件'
        return displayed_values

# 旧DB同期と初期投入で共有する設定値と表示用の補助関数。

SOURCE_DATABASE = 'etenki'
TARGET_DATABASE = 'default'
BATCH_SIZE = 500
MAX_DISPLAY_VALUES = 20


# エラー表示用に値の一覧を指定件数まで短縮する。
def format_limited_values(values, *, limit=MAX_DISPLAY_VALUES):
    if not values:
        return 'なし'

    displayed_values = ', '.join(str(value) for value in values[:limit])
    remaining_count = len(values) - limit
    if remaining_count > 0:
        return f'{displayed_values} ほか{remaining_count}件'
    return displayed_values

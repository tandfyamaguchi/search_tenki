# 「天気」記事検索 — 導入・初期設定

この文書は、アプリケーションを新しい環境へ導入する担当者向けです。日常のデータ管理、Django admin の操作、バックアップの判断基準は [README.md](README.md) を参照してください。

## 1. 構成とデータの扱い

初回導入時だけ、空の検索用DBへ初期データを投入してから旧DBを同期します。同期完了後の編集はDjango admin（`/admin/`）で行い、旧DB同期を再実行しません。

|対象|用途|運用上の扱い|
|---|---|---|
|`db.sqlite3`|検索記事、巻・号、カテゴリ・原稿種別、認証、adminの操作履歴を保持する運用DB|読み書き可|
|`etenki.db`|旧データの参照元（`kiji`、`naiyou`）|変更禁止の参照用データ|
|`maketable/`|初回導入専用のCSVと`initialize_search_db`コマンド|初回導入以外では使用しない|
|`static/`|`collectstatic` が出力する静的ファイル|Webサーバーが配信する|

> **重要:** 初回導入では、テスト用や旧環境の`db.sqlite3`を配置しません。空の`db.sqlite3`へ`migrate`を適用した後、`initialize_search_db`を実行します。このコマンドは、`etenki.db`の記事ID・内容分類IDを保った初期レコード、カテゴリ、巻・号を投入し、そのまま旧DBの内容を同期します。`etenki.db`は読み取り専用で、コマンドは変更しません。

`list.0006_category_group_admin` は初回の原稿種別25件を作成します。続く`initialize_search_db`が、承認済みの`category.csv`にあるカテゴリID 1〜206へ原稿種別を付けて投入します。`list.0007_require_category_group`により、カテゴリは原稿種別なしで保存できません。初期投入中にエラーが出た場合は本番DBを手作業で変更せず、空のステージングDBと`maketable/`内のCSV、`etenki.db`を確認してください。

## 2. 環境構築

以下のテスト環境と同じ構成を作る手順です。

- Minicondaの `search-tenki-dj52` 環境
- Python 3.12
- Django 5.2 LTS

### Minicondaの導入

[Anaconda公式のMiniconda配布ページ](https://www.anaconda.com/download) から取得してください。

### `search-tenki-dj52` 環境の作成

```sh
cd ./search_tenki

# Python 3.12の専用環境を作成する（初回だけ）
conda create -n search-tenki-dj52 python=3.12 -y

# 以後、このプロジェクトの操作前に有効化する
conda activate search-tenki-dj52

python -m pip install --upgrade pip
python -m pip install "Django>=5.2,<5.3"
python --version
python -m django --version
```
以後の `python manage.py` コマンドは、すべて `conda activate search-tenki-dj52` を実行した状態で使用します。

## 3. プログラム類の導入

GitHubの
https://github.com/tandfyamaguchi/search_tenki/tree/202609
の「Code」＞「Download Zip」で、プログラム類をダウンロードします。
`db.sqlite3`は削除して、./search_tenkiに保存します。
初回導入では、既存・同梱の`db.sqlite3`をコピーしません。後述の手順で空の`db.sqlite3`を作成します。

## 4. 本番用環境変数

本番ではアプリケーションプロセスの起動前に、次の3つを設定します。値はシークレット管理機能またはサーバーの安全な環境設定に保存し、ソースコード、README、シェル履歴へ記録しません。

```sh
export DJANGO_DEBUG=0
export DJANGO_SECRET_KEY='<シークレット管理機能から渡す値>'
export DJANGO_ALLOWED_HOSTS='search.example.invalid,admin.example.invalid'
```

- `DJANGO_DEBUG` は `1` / `true` / `yes` / `on` または `0` / `false` / `no` / `off` を受け付けます。
- `DJANGO_ALLOWED_HOSTS` はカンマ区切りです。本番では空にできません。
- `DJANGO_DEBUG=0` のとき、`DJANGO_SECRET_KEY` または `DJANGO_ALLOWED_HOSTS` が未設定なら起動時に失敗します。

確認コマンド:
```sh
python manage.py check --deploy
```

## 5. 空DBの作成、初期同期、静的ファイル、管理者アカウント
本番へ適用する前に、テスト環境で次を実行します。

```sh
cd ./search_tenki
conda activate search-tenki-dj52

# 既存の運用DBを上書きしないことを確認して、空DBを作成する
test ! -e db.sqlite3
touch db.sqlite3

# 予定されるスキーマ変更を確認する
python manage.py migrate --database=default --plan

# 承認されたスキーマ変更だけを適用する
python manage.py migrate --database=default

# 初期投入と旧DB同期を検証する。検索用DBへの変更はロールバックされる
python manage.py initialize_search_db --dry-run

# 検証結果を承認後、初期投入と旧DB同期を確定する
python manage.py initialize_search_db --apply

# Webサーバーが配信する静的ファイルを集約する
python manage.py collectstatic --noinput
```

`migrate --database=etenki` は絶対に実行しないでください。旧DBに本来不要なテーブルを作成するおそれがあります。通常の運用DBは必ず `default`（`db.sqlite3`）です。

`migrate`直後の空DBには、原稿種別25件だけが作成され、カテゴリ・記事・内容分類・巻・号はまだありません。`initialize_search_db`は、すべての`default`マイグレーションが適用済みで、これらの初期投入対象テーブルが空であることを確認してから実行します。既存データがある場合は停止するため、テスト用や運用中のDBを上書きしません。

### 初回導入専用コマンド

初回のみ使用するCSVとコマンドはすべて`maketable/`にまとめています。`initialize_search_db`は、記事ID・内容分類IDを`etenki.db`と同じ値で作成し、`category.csv`、`makeyear.csv`、`makemonth.csv`からカテゴリ・巻・号を投入した後、既存の同期処理を実行します。CSVは承認済みの固定初期データであり、内容を変更したり同フォルダーの旧シェルスクリプトで再生成したりしません。初期投入と同期は1つのトランザクションなので、失敗時や`--dry-run`時に`db.sqlite3`へ途中データは残りません。

旧DBにある著者・キーワードの表記は、初回同期時に整形せずそのまま引き継ぎます。旧DBのデータを修正する必要がある場合は、同期完了後にDjango adminで管理します。

`initialize_search_db`は`--dry-run`または`--apply`のどちらかを必ず指定します。`--apply`は空DBに対して一度だけ実行します。初回同期後は、`initialize_search_db`と`makemodel`を再実行してはいけません。以後の記事・巻・号・カテゴリ・内容分類・キーワードの更新はadminで行います。

`etenki.db`にだけ存在するカテゴリや、CSV・原稿種別の不整合がある場合、`initialize_search_db`は書き込み前に停止します。CSVや本番DBを手作業で変更せず、原因を確認してから初回導入をやり直してください。

初回の管理者アカウントは、空DB作成、マイグレーション、初回同期を完了した後に作成します。パスワードは対話入力し、コマンドライン引数に渡しません。

```sh
python manage.py createsuperuser --username '<管理者ID>'
```

`createsuperuser` で作成した利用者は、adminへのログインと全管理権限を持ちます。共用アカウントや同梱DB中の既存アカウントを流用せず、担当者ごとに個別アカウントを作成してください。権限を絞る運用は、初期管理者がadminの「ユーザー」「グループ」で設定します。

## 6. ローカル環境でのテスト実行
```sh
python manage.py test
python manage.py check
python -Wa manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py runserver 127.0.0.1:8000 --noreload
```

http://127.0.0.1:8000/ で、以下を確認します。

1. トップ画面、巻・号検索、詳細検索が表示されること。
2. 静的ファイル（CSS、画像、Django adminの装飾）が読み込まれること。
3. `/admin/` で作成した個別管理者アカウントがログインできること。
4. adminで許可されたモデルだけが表示されること。操作対象と必要な権限の詳細は [README.md](README.md) を参照してください。

## 7. Webサーバーへの接続

静的ファイルの出力先は `STATIC_ROOT`（このプロジェクトでは `static/`）です。`collectstatic` の後、Webサーバーがこの出力先の静的URLを配信できるよう設定してください。Djangoアプリケーションだけで本番用静的ファイルを配信する構成にはしません。

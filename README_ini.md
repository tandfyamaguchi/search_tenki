# 「天気」記事検索 — 導入・初期設定

本番環境の構築・導入する方法を説明する。Django admin を使う日常のデータ管理は [README.md](README.md)、実装とDjangoの設計は [README_prog.md](README_prog.md) を参照してください。

「プロジェクトルート」は、`manage.py`、`mysite/`、`list/` があるディレクトリを指します。

## 1. 導入前の前提

### 旧データの受渡し

初回投入で参照する旧データは `etenki.db` です。

|旧テーブル|必要な主な列|用途|
|---|---|---|
|`kiji`|`id`、`bunrui`、`category`、`title_jp`、`author_jp`、`volume`、`start_page`、`no`、`keyword`、`pdf`|記事と関連値の初期同期元|
|`naiyou`|`id`、`title`|内容分類の初期同期元|

etenki.dbは、本番環境に搭載する直前に再度作成していただく必要があります。なお、etenki.dbは、 エラーが出ますので、[README_prog.md](README_prog.md)の下部記載のように、あらかじめ修正をお願いします。
`basemodel/initial_data/years.csv`と`months.csv` は第66巻（2019年）までです。初期同期を行う前に、最新まで追加する必要があります。

## 2. 構成とデータの扱い

新規導入では、空の検索用DBへスキーマと初期データを作成してから、旧DBを一度だけ同期します。同期完了後の編集はDjango admin（`/admin/`）で行い、旧DB同期を再実行しません。

|対象|用途|運用上の扱い|
|---|---|---|
|`db.sqlite3`|検索記事、巻・号、カテゴリ・原稿種別、認証、adminの操作履歴を保持する運用DB|サービスアカウントが読み書きする。|
|`etenki.db`|旧データの参照元（`kiji`、`naiyou`）|読取り専用。初回同期後の通常運用では更新しない。|
|`basemodel/initial_data/`|原稿種別、カテゴリ、巻、号の承認済み初期データCSV|初回投入専用。|
|`basemodel/management/commands/initialize_search_db.py`|空の検索用DBを構成し旧DBを同期するコマンド|初回導入時だけ使用する。|
|各アプリ内の`static/`|CSS、JavaScript、画像の元ファイル|ソースとして管理する。|
|`static/`|`collectstatic` の出力先|Webサーバーが配信する。直接編集しない。|

`initialize_search_db` は、まず `category_groups.csv` の原稿種別25件を作成し、`categories.csv` のカテゴリID 1〜206へ原稿種別を対応付けます。続いて、`etenki.db` の記事ID・内容分類IDを維持した初期レコード、カテゴリ、巻・号を投入し、旧DBの内容を同期します。カテゴリは原稿種別なしで保存できません。処理全体は1つのトランザクションなので、失敗時または `--dry-run` 時に途中データは残りません。

## 3. プログラムの取得とリリース配置

1. プログラムは、[GitHubの `202609` ブランチ](https://github.com/tandfyamaguchi/search_tenki/tree/202609) の「Code」→「Download ZIP」で取得してください。
2. ZIPを展開し、`manage.py` があるディレクトリを本番のリリースディレクトリ（例: `./search_tenki`）として配置します。プロジェクトルートをWebサーバーのDocumentRootとして公開せず、静的ファイル用の `static/` だけを公開パスへ対応付けます。これにより、SQLiteファイルやソースコードの直接公開を防ぎます。
3. `etenki.db` と `basemodel/initial_data/` が揃っていることを確認します。
4. GitHubから取得したフォルダー内の `db.sqlite3` は削除してしてくだい。後述の手順の通り、空の `db.sqlite3` を作成するようにしています。

## 4. Python環境の構築

以下のテスト環境と同じ構成を作る手順です。

- Minicondaの `search-tenki-dj52` 環境
- Python 3.12
- Django 5.2 LTS
Minicondaは [公式配布ページ](https://www.anaconda.com/download) から取得してください。

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
以後の `python manage.py` コマンドは、対象のPython環境を有効化した状態で実行します。

## 5. 本番用環境変数

本番でのサーバーの設定推奨

|環境変数|本番での値|役割|
|---|---|---|
|`DJANGO_DEBUG`|`0`|詳細なデバッグ表示を無効にする。|
|`DJANGO_SECRET_KEY`|Django内部の署名に使う秘密のランダム文字列|セッション等の署名に使う。|
|`DJANGO_ALLOWED_HOSTS`|公開するドメイン名|Hostヘッダーを検証する。|

次は値の形式を示す例です。
```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY='<シークレット管理機能から渡す値>'
DJANGO_ALLOWED_HOSTS='<公開ホスト名>,<管理画面を別ホストにする場合のホスト名>'
```
`DJANGO_DEBUG=0` のとき、`DJANGO_SECRET_KEY` または `DJANGO_ALLOWED_HOSTS` が未設定だと、設定読み込み時に失敗します。

## 6. 新規DBの作成と初期データ投入

`etenki.db` と初期CSVがあること、かつ **稼働用の `db.sqlite3` が存在しないこと** を確認してください。既存の運用DBがある環境には、この手順を適用しません。

```sh
cd ./search_tenki
conda activate search-tenki-dj52

# 既存DBを上書きしない。存在した場合はここで停止する。
test ! -e db.sqlite3

# 設定・スキーマ変更予定を確認する。
python manage.py check
python manage.py migrate --database=default --plan

# 承認済みのスキーマだけを空のdefault DBへ作成する。
python manage.py migrate --database=default

# 初期投入と旧DB同期をロールバック付きで検証する。
python manage.py initialize_search_db --dry-run

# 検証結果を承認後、空のDBへ一度だけ確定する。
python manage.py initialize_search_db --apply

# Webサーバー配信用の静的ファイルを集約する。
python manage.py collectstatic --noinput

# 管理者を対話入力で作成する。
python manage.py createsuperuser --username '<管理者ID>'
```

`migrate --database=etenki` は実行しないでください。DBルーターは旧DBへのmigrationを拒否し、旧DB接続もSQLiteの読取り専用設定です。通常の運用DBは必ず `default`（`db.sqlite3`）です。

`initialize_search_db` は `--dry-run` または `--apply` のどちらかを必ず指定します。`--apply` は空DBに対して一度だけ実行します。同期後の記事・巻・号・カテゴリ・内容分類・キーワードの更新はDjango adminで行います。初回同期後にこのコマンドを再実行すると、運用中のデータを混在させるおそれがあるため実行しません。

初期投入前または同期中の検証で、`etenki.db` のカテゴリがCSVにない、原稿種別の対応がない、IDが不整合であるなどの問題を検出すると、コマンドはトランザクションをロールバックして変更を残さず停止します。本番DBを手作業で変更せず、空のDBでやり直してください。

## 7. WebサーバーとWSGIの接続

```text
利用者
  └─ HTTPS対応Webサーバー / リバースプロキシ
       ├─ /static/  ───────────────→ <プロジェクトルート>/static/
       └─ その他のDjango URL ──────→ WSGIアプリケーションサーバー
                                         └─ mysite.wsgi:application
                                              ├─ db.sqlite3 (通常運用DB)
                                              └─ etenki.db (初回投入時の読取り専用参照元)
```

|担当範囲|必須事項|
|---|---|
|Webサーバー／リバースプロキシ|TLS、公開URLからDjangoへの転送、`/static/` のファイル配信、アクセスログを設定する。|
|WSGIアプリケーションサーバー|作業ディレクトリをプロジェクトルートにし、対象のPython環境で `mysite.wsgi:application` を読み込む。|
|プロセス管理|環境変数を安全に渡し、起動・停止・再起動、異常終了時の再起動、アプリケーションログを管理する。|
|Djangoアプリケーション|URL処理、検索、admin、DBアクセスを担当する。`asgi.py` はありますが、現行の公開構成はWSGIを前提としています。|

`STATIC_ROOT` は `<プロジェクトルート>/static/` です。`collectstatic` 後に、Webサーバーがこの絶対パスを `/static/` として配信できるよう設定してください。PDFはアップロードしません。記事の `pdf` に保存した相対パスと設定済みの外部PDF基底URLを組み合わせてリンクします。

テンプレートはBootstrap、jQuery、Popper.jsを外部CDNからも読み込みます。

## 8. セキュリティ確認と受入テスト

公開前に、本番と同じ環境変数をサービス定義から読み込ませて、次を実行します。

```sh
python manage.py check
python manage.py check --deploy
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

`check --deploy` では、本番用設定で HSTS、HTTPSリダイレクト、セッションCookieの`Secure`属性、CSRF Cookieの`Secure`属性に関する警告が出ます。HTTPS終端とプロキシヘッダー（リバースプロキシの場合は `SECURE_PROXY_SSL_HEADER` を含む）の設計を確定し、必要な `settings.py` の変更をレビュー・テストしてから対処してください。HSTSは誤設定時の影響が大きいため、検証なしで有効化しません。

### 確認事項
1. `/`、巻・号検索、詳細検索、検索結果、`/search/copyright/` が表示されること。
2. CSS、画像、Django adminの静的ファイルが `/static/` から読めること。
3. PDFリンク、分類・著者・キーワードからの絞込み、詳細検索の並び順・表示件数・リセットが動くこと。
4. `/admin/` に個別の管理者アカウントでログインでき、不要なモデルが表示されないこと。
5. 意図しないHost名ではアクセスを拒否し、エラー画面に詳細情報が出ないこと。

## 9. 本番反映、更新、ロールバック

新規導入と、既にDjango版を運用している環境の更新は区別します。既存環境では `initialize_search_db` を実行せず、稼働中の `db.sqlite3` を置き換えません。通常の更新、バックアップ、復元は [README.md](README.md) の手順に従ってください。
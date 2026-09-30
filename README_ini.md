# 「天気」記事検索 — 導入・初期設定

この文書は、アプリケーションを新しい環境へ導入する担当者向けです。日常のデータ管理、Django admin の操作、バックアップの判断基準は [README.md](README.md) を参照してください。

## 1. 構成とデータの扱い

このアプリケーションは Django による記事検索サイトです。公開画面は検索専用です。初回導入時にはPythonの同期コマンドで旧DBから検索用DBへ同期し、稼働開始後の巻・号などの通常操作は Django admin（`/admin/`）で行います。adminで操作できる範囲と制限は [README.md](README.md) を参照してください。

|対象|用途|運用上の扱い|
|---|---|---|
|`db.sqlite3`|検索記事、巻・号、認証、admin の操作履歴を保持する運用DB|永続領域に置き、アプリケーション実行ユーザーだけに読み書きを許可する|
|`etenki.db`|旧データの参照元（`kiji`、`naiyou`）|変更禁止の参照用データとして扱い、OSのファイル権限で書き込みを禁止する|
|`static/`|`collectstatic` が出力する静的ファイル|Webサーバーが配信する|

現行の設定では、DBのパスはアプリケーション直下の固定名です。新しいリリースを配置するときに、稼働中の `db.sqlite3` や `etenki.db` を無条件で上書きしてはいけません。導入前に、データ担当者が承認した同一時点の2ファイルを対として用意してください。

`etenki.db` はコード上でSQLiteの強制読み取り専用モードにはなっていません。Django admin の操作対象でもありませんが、ファイルを直接操作すれば変更できてしまいます。アプリケーション実行ユーザーにこのファイルの書き込み権限を与えないでください。

> **重要:** 初回導入では `makemodel` で旧DBから検索用DBへ同期します。ただし、このコマンドは空の `db.sqlite3` を初期投入するものではありません。旧DBと検索用DBの記事ID・内容分類IDが一致することを最初に確認するため、`migrate` 直後の空DBに対して実行すると失敗します。同期前に、ID集合が対応済みの初期 `db.sqlite3`（同梱の初期データまたは承認済みのベースDB）を配置してください。

## 2. 導入前の準備


- インターネット公開時は、HTTPS終端、HTTPからHTTPSへの誘導、adminへのアクセス制限を担うリバースプロキシまたはPaaSの設定を用意します。
- SQLiteは同時書き込みに向きません。admin操作、バックアップ、リリース時のDB更新が重ならない運用としてください。複数の書き込み系アプリケーションプロセスを同時に動かさないでください。
- バックアップの保存先は、アプリケーション配置先とは別の永続領域を使用します。復元手順は本番投入前にステージング環境で確認してください。

このリポジトリには、Webサーバー、WSGIワーカー、サービス管理、コンテナの設定は含まれていません。これらはインフラ担当者が組織の標準に従って用意します。WSGIの起点は `mysite.wsgi:application` です。

## 3. 環境構築

以下のテスト環境と同じ構成を作る手順です。
- Miniconda の `search-tenki-dj52` 環境
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

次に、 `db.sqlite3` と `etenki.db` を配置します。初回同期前の `db.sqlite3` は、`etenki.db` と記事ID・内容分類IDが対応したベースDBでなければなりません。`db.sqlite3` と、そのSQLiteのジャーナルファイルを作成できるディレクトリには、アプリケーション実行ユーザーの書き込み権限が必要です。一方、`etenki.db` は実行ユーザーが読めるが書けない権限にします。

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

現行コードにはHTTPS強制、HSTS、Secure Cookie、プロキシのHTTPSヘッダー設定は含まれていません。インターネット公開前に `python manage.py check --deploy` を実行し、表示される警告への対処方針をインフラ担当者とアプリケーション担当者で確認してください。adminは少なくともHTTPS、VPNまたはIP制限などで保護します。

## 5. スキーマ、初期同期、静的ファイル、管理者アカウント

以下のコマンドは、まずステージング環境で実施・確認します。本番で実行する場合は、DBバックアップと変更承認の後に限ります。

```sh
cd ./search_tenki
conda activate search-tenki-dj52

# 予定されるスキーマ変更を確認する
python manage.py migrate --database=default --plan

# 承認されたスキーマ変更だけを適用する
python manage.py migrate --database=default

# Webサーバーが配信する静的ファイルを集約する
python manage.py collectstatic --noinput
```

`migrate --database=etenki` は絶対に実行しないでください。旧DBに本来不要なテーブルを作成するおそれがあります。通常の運用DBは必ず `default`（`db.sqlite3`）です。

### 初回導入時の旧DB同期

ベースDBを配置し、`default` のマイグレーションを確認した後、初回導入時に限って旧DBとの同期を行います。adminで巻・号の運用を始める前に、必ず検証モードから実行してください。

```sh
# 同期内容を検証する。検索用DBへの変更はロールバックされる
python manage.py makemodel --dry-run

# 検証結果を承認後、旧DBの内容を検索用DBへ同期する
python manage.py makemodel

# 同期後のカテゴリ設定を読み取り専用で確認する
python manage.py validate_category_groups
```

通常の `makemodel` は `db.sqlite3` を更新します。初回同期が終わった後は、旧DBのデータを更新する必要が生じた場合を除き、通常のリリースや巻・号追加のためにこのコマンドを実行しません。再同期が必要な場合の承認・バックアップ手順は [README.md](README.md) を参照してください。

初回の管理者アカウントは、DBを配置し、マイグレーションと初回同期を完了した後に作成します。パスワードは対話入力し、コマンドライン引数に渡しません。

```sh
python manage.py createsuperuser --username '<管理者ID>'
```

`createsuperuser` で作成した利用者は、adminへのログインと全管理権限を持ちます。共用アカウントや同梱DB中の既存アカウントを流用せず、担当者ごとに個別アカウントを作成してください。権限を絞る運用は、初期管理者がadminの「ユーザー」「グループ」で設定します。

## 6. Webサーバーへの接続

本番では `python manage.py runserver` を使用しません。インフラ担当者が選んだWSGI対応のアプリケーションサーバーから、`search-tenki-dj52` 環境のPythonで `mysite.wsgi:application` を起動し、リバースプロキシ経由で公開します。

静的ファイルの出力先は `STATIC_ROOT`（このプロジェクトでは `python_GPT2/static/`）です。`collectstatic` の後、Webサーバーがこの出力先の静的URLを配信できるよう設定してください。Djangoアプリケーションだけで本番用静的ファイルを配信する構成にはしません。

adminを公開経路に置く場合は、公開検索画面と同じドメインでも別のドメインでも構いませんが、`DJANGO_ALLOWED_HOSTS` にアクセスに使うホスト名を含めます。実在する本番URLをこの文書へ記載しないでください。

## 7. 導入後の確認

本番データを変更しない確認から順に実施します。

```sh
python manage.py check
python manage.py check --deploy
python manage.py validate_category_groups
```

`validate_category_groups` は読み取り専用です。テストはテスト用DBを作成するため、本番環境ではなくステージング環境で実施します。

```sh
python manage.py test
```

ブラウザーでは、次を確認します。

1. トップ画面、巻・号検索、詳細検索が表示されること。
2. 静的ファイル（CSS、画像、Django adminの装飾）が読み込まれること。
3. `/admin/` で作成した個別管理者アカウントがログインできること。
4. adminで許可されたモデルだけが表示されること。操作対象の詳細は [README.md](README.md) を参照してください。

## 8. 更新時のチェックリスト

1. リリース対象と、永続化する `db.sqlite3`・`etenki.db` を分けて確認する。
2. 運用DBのバックアップと復元可能性を確認する。
3. ステージングで `check`、テスト、公開画面、adminログインを確認する。
4. 本番ではメンテナンス時間を設け、adminによる書き込みとDB同期を止める。
5. 必要な場合のみ `migrate --database=default` と `collectstatic --noinput` を実行する。
6. 公開後に検索、静的ファイル、adminログイン、ログを確認する。

初回導入では、上記の `makemodel` による旧DB同期を完了してからadmin運用を開始します。稼働開始後の通常リリースでは同期を含めず、旧DB更新に伴う再同期だけを [README.md](README.md) の承認手順に従って実施してください。

# 「天気」記事検索 — プログラム概要

新規導入と本番切替は [README_ini.md](README_ini.md)、Django adminを使う日常管理は [README.md](README.md) を参照してください。

## 1. Djangoの基本設計とこのプロジェクトでの対応

Djangoは、URL、View、Model、Templateを分けるMVT（Model-View-Template）設計です。このプロジェクトでは、各画面のViewは主に関数として実装しています。

```text
ブラウザーからのHTTPリクエスト
  → mysite/urls.py
  → 各アプリの urls.py
  → views.py のView関数
  → forms.py による入力検証 / models.py のORMによるDB操作
  → templates/ のHTMLレンダリング
  → HTTPレスポンス
```

|Djangoの要素|このプロジェクトでの役割|
|---|---|
|プロジェクト|`mysite/`。全体設定、ルートURL、WSGI入口、DBルーターを持つ。|
|アプリ|機能単位の `home`、`search`、`list`、`basemodel`。`INSTALLED_APPS` に登録する。|
|URLconf|`mysite/urls.py` がアプリへ振り分け、各アプリの `urls.py` がView関数へ対応付ける。|
|View|リクエストを受け、入力を検証し、DBから取得した値をテンプレートへ渡す。|
|Model / ORM|PythonクラスでDBテーブルと関連を表す。SQLを直接組み立てず、通常はQuerySetを使う。|
|Form|詳細検索のGETパラメータを検証・正規化し、テンプレートの入力部品も生成する。|
|Template|HTML。Viewから受け取ったコンテキストを表示し、`{% static %}` と `{% url %}` でパスを生成する。|
|Migration|Modelのスキーマ変更を履歴として管理する。`default` DBだけに適用する。|
|Admin|モデル管理用のDjango標準画面を、`admin.py` で本システムの運用向けに拡張する。|

Webサーバーは `mysite.wsgi:application` を呼び出します。`settings.py` は環境変数、DB、テンプレート、静的ファイルなどの共通設定を読み込みます。詳細な本番接続は [README_ini.md](README_ini.md) を参照してください。

## 2. ディレクトリ構成

```text
<プロジェクトルート>/
├── manage.py                         # Django管理コマンドの入口
├── mysite/                           # プロジェクト全体の設定
│   ├── settings.py                   # 環境変数、DB、静的ファイル等
│   ├── urls.py                       # ルートURLの振分け
│   ├── wsgi.py                       # 本番用WSGI入口
│   ├── asgi.py                       # ASGI入口（現行公開構成では未使用）
│   └── db_router.py                  # default / etenki の振分け
├── home/                             # トップ画面
│   ├── templates/base.html
│   ├── templates/home/index.html
│   └── static/                       # 共通CSS、画像、検索UIのJavaScript
├── search/                           # 巻・号検索、詳細検索、発行管理
│   ├── forms.py
│   ├── models.py                     # Year、Month
│   ├── views.py
│   ├── admin.py
│   ├── templates/search/
│   └── static/search/
├── list/                             # 検索結果、記事とマスタの管理
│   ├── models.py                     # Kijis、Category等
│   ├── views.py
│   ├── sorting.py                    # 記事一覧の並び替え
│   ├── admin.py
│   ├── templates/list/
│   └── static/list/
├── basemodel/                        # 旧DBの読取り専用モデルと初回同期
│   ├── models.py
│   ├── initial_data/                 # 原稿種別、カテゴリ、巻、号のCSV
│   ├── services/legacy_sync.py
│   └── management/commands/initialize_search_db.py
└── static/                           # collectstaticの出力先。直接編集しない。
```

各アプリ内の `static/` は編集対象の元ファイルです。プロジェクト直下の `static/` は `collectstatic` が集約する配信用出力であり、修正は必ず各アプリ内の `static/`側で行います。

## 3. 画面、URL、処理の流れ

|URL|View|処理|
|---|---|---|
|`/`|`home.views.HomeView`|トップ画面を表示する。|
|`/search/volume/`|`search.views.SelectYearView`|発行年・巻の一覧を表示する。|
|`/search/no/<year_id>/`|`search.views.SelectNoView`|選択した巻に属する号を表示する。|
|`/search/detail/`|`search.views.SearchDetailView`|詳細検索フォームを表示する。|
|`/search/copyright/`|`search.views.CopyrightView`|著作権案内を表示する。|
|`/list/list1/<id>/`|`list.views.ShowListView1`|選択した号の記事一覧を表示する。|
|`/list/list2/`|`list.views.ShowListView2`|詳細検索条件に一致する記事一覧を表示する。|
|`/list/list3/<id>/<shurui>/`|`list.views.ShowListView3`|内容分類、著者、キーワードから記事を絞り込む。|
|`/admin/`|Django admin|記事、マスタ、巻・号、利用者を管理する。|

### 公開検索の主な流れ

1. 巻・号検索では `Year` と `Month` を選び、号IDを `ShowListView1` へ渡す。
2. 詳細検索では `SearchDetailForm` が入力を検証し、`ShowListView2` が条件を順にQuerySetへ適用する。
3. 一覧表示では `list/views.py` が関連データをまとめて取得し、ページ分割、著者表示順の付与、並び替えを行う。
4. `list/templates/list/ShowList1.html` が共通の結果表を表示し、`_result_header.html` が見出し、`page.html` がページネーションを担当する。

## 4. 検索フォームと並び替え

`search/forms.py` の `SearchDetailForm` は、内容分類、カテゴリ、タイトル、著者、巻、号、キーワード、並び順、表示件数を検証します。

- タイトル、著者、キーワードの同じ入力欄では、空白区切りをAND検索、独立した大文字の `OR` をOR検索、語頭の半角ハイフンを除外検索として扱います。
- 異なる入力欄の条件はANDで組み合わせます。複数選択したカテゴリ、巻、号は各選択肢のいずれかに一致する記事を対象にします。
- 多対多の検索で生じる重複記事は `distinct()` で1件にまとめます。
- `list/sorting.py` は、巻・号・開始頁を数値として並べ、文字列列ではSQLite用の簡易な日本語・英字・数字の自然順照合を登録します。
- ページ番号、表示件数、見出しの並び替えURLは、現在の検索条件を保持します。

入力仕様を変えると、`search/forms.py`、`list/views.py`、テンプレート、テストの整合を同時に確認してください。

## 5. 主なモデルと関連

公開検索・adminで使うモデルは `default` の `db.sqlite3` に保存します。

```text
Year (発行年・巻)
  └─ 1 : N ─ Month (号・開始頁)

CategoryGroup (原稿種別)
  └─ 1 : N ─ Category (カテゴリ)
                 └─ 1 : N ─ Kijis (記事)
                                  ├─ N : M ─ Bunrui (内容分類)
                                  ├─ N : M ─ Author (著者)
                                  │             ※ ArticleAuthor が公開表示順を保持
                                  └─ N : M ─ Keyword (キーワード)
```

|モデル|主な役割・制約|
|---|---|
|`search.Year`|発行年と巻番号を保持する。巻番号は一意で、負数を許可しない。|
|`search.Month`|`Year`に属する号と開始頁を保持する。同じ巻に同じ号番号は登録できない。|
|`list.Kijis`|記事本体。題名、巻、号、開始頁、PDF相対パス、カテゴリ、内容分類、著者、キーワードを持つ。|
|`list.CategoryGroup`|詳細検索のカテゴリをまとめる原稿種別。名称と表示順は一意。|
|`list.Category`|記事のカテゴリ。原稿種別へのForeignKeyは必須で、使用中のカテゴリは保護される。|
|`list.Bunrui`、`Author`、`Keyword`|記事に関連付ける内容分類、著者、キーワードのマスタ。|
|`list.ArticleAuthor`|記事と著者の中間モデル。著者の公開順を保持する。|

`Kijis.volume` と `Kijis.no` は既存データとの互換性のため文字列型です。検索・表示時に数値として扱う必要がある箇所は、`list/sorting.py` やadminの処理で明示的に変換しています。

## 6. 2つのDBと初回同期

このシステムは、通常運用DBと旧データ参照DBを分離しています。

|DB別名|ファイル|用途|書込み|
|---|---|---|---|
|`default`|`db.sqlite3`|公開検索、admin、認証、運用データ|可|
|`etenki`|`etenki.db`|PHP版から引き継ぐ旧記事・内容分類の初回同期元|不可|

`mysite/db_router.py` は `basemodel` のモデルだけを `etenki` へ、それ以外を `default` へ振り分けます。`basemodel` は `managed = False` の読取り専用モデルであり、Django migrationの対象ではありません。通常のmigrationは `default` にだけ適用します。

初回導入では `initialize_search_db` が次の順に実行されます。

1. すべての `default` migration が適用済みで、初期投入対象テーブルが空であることを検証する。
2. `category_groups.csv`、`categories.csv`、`years.csv`、`months.csv` を検証して投入する。
3. 旧DBの記事ID・内容分類IDを保った空のレコードを作る。
4. `LegacySynchronizer` が旧DBの本文項目、カテゴリ、内容分類、著者、キーワード、著者の表示順を検索用DBへ同期する。
5. `--dry-run` ではトランザクションをロールバックし、`--apply` では確定する。

`etenki.db` は初期同期元であり、日常運用の差分同期元ではありません。初回同期後の追加・修正はadminで行うため、既存の運用DBに対して初期化コマンドを再実行しません。

## 7. Django adminの実装

`search/admin.py` は巻を起点に号と記事を管理できる画面を定義します。記事が存在する巻・号の番号変更や削除を防ぎ、号は単独の管理メニューではなく巻詳細から管理します。

`list/admin.py` は記事と関連マスタの管理を定義します。主な保護・補助は次のとおりです。

- 記事追加時に選択した巻に属する号だけを選べるようにする。
- `ArticleAuthor` のインラインで著者と公開表示順を入力し、重複を防ぐ。
- 使用中のカテゴリ、内容分類、キーワード、原稿種別、著者を不用意に削除できないようにする。
- 巻・号の画面から記事を追加・編集した場合、入力破棄後に親の巻画面へ戻す。
- admin一覧の関連件数を集計して表示し、一覧表示時のN+1クエリを避ける。

管理画面の操作方法と権限管理は [README.md](README.md) を参照してください。

## 8. 設定、テンプレート、静的ファイル

`mysite/settings.py` は次を設定します。

- `DJANGO_DEBUG`、`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS` を環境変数から読む。本番では3つすべてが必要。
- SQLiteの `default` と読取り専用URIの `etenki` を設定する。
- `LANGUAGE_CODE='ja'`、`TIME_ZONE='Asia/Tokyo'` を使う。
- `STATIC_ROOT` をプロジェクト直下の `static/` に設定する。
- 記事PDFの基底URLを `PDF_URL` として設定する。PDFアップロード用の`MEDIA_ROOT`や`MEDIA_URL`はない。

テンプレートは、トップ画面用の `home/templates/base.html` と、検索画面用の `search/templates/search/base.html` を基礎にします。検索画面用のベーステンプレートはBootstrap、jQuery、Popper.jsをCDNから読み込みます。

## 9. 改修時の手順と確認

モデルを変更した場合は、意図したmigrationを作成・レビューしてから適用します。既存の初期migrationや運用DBを手作業で編集して整合させるのではなく、Djangoのmigrationとして変更を表します。旧DBの `basemodel` はmigration対象にしません。

変更後は、対象のPython環境で少なくとも次を実行します。

```sh
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

テンプレート、CSS、JavaScriptを変更した場合は、元ファイルを修正した後に `collectstatic` を実行し、ブラウザーで静的ファイルが更新されていることを確認します。本番投入前には [README_ini.md](README_ini.md) の受入テストと `check --deploy` を行ってください。

#---------------
etenki.dbの改良
以下の点を変更しないと、SQLに変更する時にエラーが出る。

Naiyouのcodeをidに変更(管理画面に表示するときにidがないとエラーが出るため)

Naiyouにないbunruiがあったり重複したりしているため、削除
id=933, bunrui='1092110921'からbunrui=''
id=1022, bunrui='1091,1091'からbunrui='1091'
id=6651, bunrui='404,513,5012'からbunrui='404,5012'
id=9267, bunrui='1019,304'からbunrui='304'
id=9588, bunrui='5913,4011,412'からbunrui='4011,412'
id=9834, bunrui='602,700,306'からbunrui='602,306'
id=1040203049, bunrui='4,0'からbunrui='4'
id=1040203354, bunrui='106,50'からbunrui='106'
id=1040203389, bunrui='109,1091,411,50'からbunrui='109,1091,411'
id=1040203498, bunrui='107,108,501,1601'からbunrui='107,108,501'
id=1040203957, bunrui='661'からbunrui=''
id=1040204018, bunrui='109,304,307,412'からbunrui='109,304,412'
id=1040206104, bunrui='101,103,104,1042,1052,107,1071,108,208,1071,306,4011,602'かららbunrui='101,103,104,1042,1052,107,1071,108,208,1071,306,4011,602'

Keywordが重複しているため、削除
id=5581, keyword='顕熱輸送、顕熱輸送、パラメータ化、熱収支モデル'からkeyword='顕熱輸送、パラメータ化、熱収支モデル'
id=1040202508, keyword='大気-陸域相互作用、熱水収支、物質循環、気候変動、スケーリングアップ、CMIP3、マルチ気候モデル比較、大気海洋諸現象、現在気候再現性、将来変化、TRMM、GPM、衛星降水観測、降雨レーダー、PANSY、大型大気レーダー、南極、カタバ風、ブリザード、オゾンホール、極成層圏雲、極中間圏雲（夜光雲)、オーロラ、重力波、乱流、極渦、物質循環、鉛直風、多分野連携、都市気候、ICUC、季節予報、定量的利用、大気リモートセンシング、気体濃度算出、ライダー'からkeyword='大気-陸域相互作用、熱水収支、物質循環、気候変動、スケーリングアップ、CMIP3、マルチ気候モデル比較、大気海洋諸現象、現在気候再現性、将来変化、TRMM、GPM、衛星降水観測、降雨レーダー、PANSY、大型大気レーダー、南極、カタバ風、ブリザード、オゾンホール、極成層圏雲、極中間圏雲（夜光雲)、オーロラ、重力波、乱流、極渦、鉛直風、多分野連携、都市気候、ICUC、季節予報、定量的利用、大気リモートセンシング、気体濃度算出、ライダー'

author_jpが重複しているため、削除
id=1040204046, '加藤輝之・大関崇・荻本和彦・長澤亮二・大竹秀明・早宣之・伊藤純至・加藤輝之・原旅人'からauthor_jp'加藤輝之・大関崇・荻本和彦・長澤亮二・大竹秀明・早宣之・伊藤純至・原旅人'

20200111　改良(山口)
	・レイアウトの変更
	・pdf表示のリンクを貼る
	・著者名に「他」が入っていると、リンクを貼らない
	・「特別号」のリンクを貼る
	・ヘッダーの画像の設置
	・faviconの設定
20231225
	・レイアウトの変更
	・「詳細検索」時に「巻の並び順」「ページあたり表示件数」「リセット」を設定できるようにした
ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー
フォルダー構造
/
|- manage.py
|- etenki.db
|- db.sqlite3
|- myvenv 仮想環境
|- mysite
 |- __init__.py
 |- settings.py プロジェクトの設定
 |- asgi.py
 |- dbrouter.py データベースを使い分ける
 |- urls.py URLの設定
 |-wsgi.py
|- home
 |-migration,static,__init__.py,admin.py,models.py,test.py
 |-templates
  |-home
   |-index.html
  |-base.html
 |-apps.py
 |-url.py
 |-view.py
|-list
 |-migrations,__init__.py,test.py
 |-templates
  |-list
   |-page.html
   |-ShowList.html
 |-templatetags
  |-mypaginator.py
 |-admin.py
 |-apps.py
 |-models.py
 |-url.py
 |-views.py
|-search
 |-migraions,__init__.py,test.py
 |-templates
  |-search
   |-base.html
   |-SearchDetail.html
   |-SelectNo.html
   |-SelectYear.html
 |-admin.py
 |-apps.py
 |-models.py
 |-urls.py
 |-views.py
 |-forms.py
|-maketable
 |-makeyear.sh
 |-makeyear.csv
 |-makemonth.sh
 |-makemonth.csv
 |-category.csv

#------------
views,formsの構造
serch/views.py
	SelectYearView
		入力先：SelectYear.html
		出力先：SelectYear.html（list=Yearモデル）
		全ての年(volume)一覧を取得する
	SelectNoView
		入力先：SelectYear.html（id=Year.id）
		出力先：SelectNo.html（list=選択されたvolumeのMonth,vol=id,year=選択されたyear）
		選択されたvolume(年)での月(no)一覧を取得する
	SearchDetailView
		入力先：SearchDetail.html
		出力先：SearchDetail.html(form=SearchDetailForm)
		SearchDetailFormで検索画面のフォームを作成
search/forms.py
	SearchDetailForm
		出力先：SearchDetailView
		「詳細検索」画面のフォームを作成する
list/views.py
	paginate_query
		入力先：SearchDetail.html、ShowListView1、ShowListView2、ShowListView3
		出力先：ShowListView1、ShowListView2、ShowListView3、page.html
		ページネーション用に、Pageオブジェクトを返す
	ShowListView1
		入力先：SelectNo.html
		出力先：ShowList1.html
		「年度（巻）検索」で選択された号の記事を抽出
	ShowListView2
		入力先：SearchDetail.html
		出力先：ShowList1.html
		「詳細検索」の条件に一致する記事を抽出
	ShowListView3
		入力先：ShowList1.html
		出力先：ShowList1.html
		「ShowList1.html」で選択した「内容分類・著者名・キーワード」に一致する記事を抽出
#-----------
htmlの構造
 home/base.html ベースとなるhtml　home/base.htmlで使用
 home/index.html
	最初の画面（検索画面に飛ばすためのページのため、本番ではいらない） SelectYear.htmlへ飛ぶ
 search/base.html ベースとなるhtml search/SelectYear.html, search/SelectNo.html, search/SearchDetail.html, list/ShowList1.htmlで使用
 search/SelectYear.html 巻(年)を選ぶ
 search/SelectNo.html 号を選ぶ
 search/SearchDetail.html 詳細検索の入力
 list/ShowList1.html 検索結果の表示
 list/page.html ページネーションの設定　list/ShowList1.htmlで使用
#--------------
modelの構造

 list/Kiji
	bunrui = ManyToManyField(Bunrui)
    	category = ForeignKey(Category)
	author = ManyToManyField(Author)
	keyword = ManyToManyField(Keyword)
    	title
	volume
	startpage
	no
	pdf
 list/Bunrui
 list/Category
 list/Author
 list/Keyword
 
 search/Year
	year
	volume
 search/Month
	volume = ForeignKey(Year.volume)
	no
	start_page

 basemodel/Kiji
	bunrui, category, title_jp, author_jp, volume, start_page, no, keyword, pdf
 basemodel/Naiyou
	title
#-----------------
home/static
	css
	image
		favicon.ico faviconの画像
		tenki_top.jpg ヘッターの画像
#---------
templatetags
	list/mypaginator.py urlのrequest.GETを引き継ぐ

#----------
databaseの使い分け
 mysite/db_router.py
	etenki.db -　basemodel　（現在のDB）
　	db.sqlite3 - basemodel以外
#--------

現在使用されているDBからdjangoで使用できるようにSQLに変換するプログラム（一度変換すれば、その後は利用なし）
 basemodel/management/commands/makemodel.py
　etenki.dbは「天気」のデータベース
　etenki.dbからdb.sqlite3に使いやすいように変形して、挿入
　変形したmodelはlist/models.pyに記載
	etenki.db  → db.sqlite3
	bunrui     → bunrui
	category   → category
	title_jp   → title
	author_jp  → author
	volume     → volume
	start_page → startpage
	no         → no
	keyword    → keyword
	pdf        → pdf

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
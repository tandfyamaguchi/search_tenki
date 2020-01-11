20200111　改良(山口)
	・レイアウトの変更
	・pdf表示のリンクを貼る
	・著者名に「他」が入っていると、リンクを貼らない
	・「特別号」のリンクを貼る
	・ヘッダーの画像の設置
	・faviconの設定
ーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーーー

htmlの構造
 base.html
 home/index.html 最初の画面
 search/SelectYear.html 巻(年)を選ぶ
 search/SelectNo.html 号を選ぶ
 search/SearchDetail.html 詳細検索の入力
 list/ShowList1.html 検索結果の表示
 list/page.html ページネーションの設定

templatetags
	list/mypaginator.py urlのrequest.GETを引き継ぐ


databaseの使い分け
 mysite/db_router.py
	etenki.db -　basemodel
　	db.sqlite3 - basemodel以外


使いやすいようにdatabaseを作るプログラム
 basemodel/management/commands/makemodel.py
　etenki.dbからdb.sqlite3に使いやすいように変形して、挿入
　変形したmodelはlist/models.pyに記載
	etenki.db  - db.sqlite3
	bunrui     - bunrui
	category   - category
	title_jp   - title
	author_jp  - author
	volume     - volume
	start_page - startpage
	no         - no
	keyword    - keyword
	pdf        - pdf


modelの構造
 list/Kiji
	bunrui = ManyToManyField(Bunrui)
    	category = ForeignKey(Category)
	author = ManyToManyField(Author)
	keyword = ManyToManyField(Keyword)
    	title, volume, startpage, no, pdf
 list/Bunrui
	name
 list/Category
	name
 list/Author
	name
 list/Keyword
	name
 
 search/Year
	year, volume
 search/Month
	volume = ForeignKey(Year.volume)
	no, start_page

 basemodel/Kiji
	bunrui, category, title_jp, author_jp, volume, start_page, no, keyword, pdf
 basemodel/Naiyou
	title

static
	css 空(後から使うよう)
	image
		favicon.ico faviconの画像
		tenki_top.jpg ヘッターの画像

etenki.dbの改良
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
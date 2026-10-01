from django.test import TestCase
from django.urls import reverse


# トップ画面の静的ファイルURLを確認する。
class HomeStaticPathTests(TestCase):
    # staticタグで生成したURLを表示することを確認する。
    def test_home_uses_static_urls(self):
        response = self.client.get(reverse('home:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/static/image/favicon.ico"')
        self.assertContains(response, 'src="/static/image/tenki_top.jpg"')

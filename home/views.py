from django.shortcuts import render


# サイトのトップ画面を表示する。
def HomeView(request):
    return render(request, "home/index.html")

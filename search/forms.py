#検索画面SearchDetail.htmlのフォームを設定
from django import forms
from .models import Year, Month
from list.models import Bunrui, Author, Category

EMPTY_CHOICES = (
    ('', '-'*5),
)

BUNRUI_CHOICES = Bunrui.objects.all()
CATEGORY_CHOIES = Category.objects.all()
VOLUME_CHOICES = Year.objects.all().order_by('id').reverse()
NO_CHOICES = Month.objects.filter(volume__volume=2).order_by('no')
ORDER_CHOICES = ((0, "降順"),(1, "昇順"))
PAGES_CHOICES = ((10,10),(30,30),(50,50),(100,100))

class SearchDetailForm(forms.Form):
    bun = forms.ModelChoiceField(label='内容分類', widget=forms.Select, queryset=BUNRUI_CHOICES, required=False,)
    categ = forms.ModelMultipleChoiceField(label='カテゴリ', widget=forms.SelectMultiple, queryset=CATEGORY_CHOIES, required=False,)
    title = forms.CharField(label='タイトル', widget=forms.TextInput(), max_length=20, required=False,)
    author = forms.CharField(label='著者', widget=forms.TextInput(), max_length=20, required=False,)
    vol = forms.ModelMultipleChoiceField(label='巻', widget=forms.SelectMultiple, queryset=VOLUME_CHOICES, to_field_name='volume', required=False,)
    n = forms.ModelMultipleChoiceField(label='号', widget=forms.SelectMultiple, queryset=NO_CHOICES, to_field_name='no', required=False,)
    word = forms.CharField(label='キーワード', widget=forms.TextInput(), max_length=20, required=False,)
    order = forms.ChoiceField(label='巻の並び順', widget=forms.Select, choices = ORDER_CHOICES, required=True,initial=0)
    pages = forms.ChoiceField(label='ページあたり表示件数', widget=forms.Select, choices = PAGES_CHOICES, required=True, initial=30)
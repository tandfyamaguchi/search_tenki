from django.core.management.base import BaseCommand
from ...models import Kiji, Naiyou
from list.models import Kijis, Author, Keyword, Category, Bunrui

class Command(BaseCommand):
    help = 'make list.models.Kijis'

    kiji_list = Kiji.objects.all()
    naiyou_list = Naiyou.objects.all()
    category_list = Category.objects.all()

    #ManyToManyFieldではない列をコピー
    # kijis = [Kijis(title=kiji.title_jp, volume=kiji.volume, startpage=kiji.start_page, no=kiji.no, pdf=kiji.pdf, id=kiji.id) for kiji in kiji_list]
    # Kijis.objects.bulk_create(kijis)
    
    # naiyous = [Bunrui(name=naiyou.title,id=naiyou.id) for naiyou in naiyou_list]
    # Bunrui.objects.bulk_create(naiyous)

    # kijis_list = Kijis.objects.all()
    # for categ in category_list:
    #     moji = kiji_list.filter(category__exact=categ.name).all()
    #     kijis = []
    #     if moji:
    #         for m in moji:
    #             kijis = Kijis.objects.get(id=m.id)
    #             kijis.category = categ
    #             kijis.save()

        

    #ManyToManyFieldをコピー
    for kiji in kiji_list:
        if kiji.bunrui:
            moji_list = kiji.bunrui.split(',')
            Through = Kijis.bunrui.through
            through_list = []
            for moji in moji_list:
                m = naiyou_list.get(id=moji)
                through_list.append(Through(kijis_id=kiji.id, bunrui_id=m.id))
            Through.objects.bulk_create(through_list)

        if kiji.author_jp:
            moji_list = kiji.author_jp.split('・')
            Through = Kijis.author.through
            through_list = []
            for moji in moji_list:
                m = Author.objects.get_or_create(name=moji)
                m = Author.objects.get(name=moji)
                through_list.append(Through(kijis_id=kiji.id, author_id=m.id))                
            Through.objects.bulk_create(through_list)

        if kiji.keyword:
            moji_list = kiji.keyword.split('、')
            Through = Kijis.keyword.through
            through_list = []
            for moji in moji_list:
                m = Keyword.objects.get_or_create(name=moji)
                m = Keyword.objects.get(name=moji)
                through_list.append(Through(kijis_id=kiji.id, keyword_id=m.id))
            Through.objects.bulk_create(through_list)

    def handle(self, *args, **options):
        if args:
            raise CommandError("Command doesn't accept any arguments")
        return self.handle_noargs(**options)

    def handle_noargs(self, **options):
        """
        Perform this command's actions.

        """
        raise NotImplementedError('subclasses of NoArgsCommand must provide a handle_noargs() method')
        
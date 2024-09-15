import json

from django.conf import settings
from django.core.management.base import BaseCommand

from recipes.models import Tag


class Command(BaseCommand):
    def handle(self, *args, **options):
        print('Началась загрузка ингредиентов')
        with open('data/tags.json', encoding='utf-8') as file:
            tags = json.load(file)
        for tag in tags:
            Tag.objects.bulk_create([
                Tag(name=tag['name']),
                Tag(slug=tag['slug'])],
                ignore_conflicts=True
            )

        print('Загрузка ингредиентов закончилась')
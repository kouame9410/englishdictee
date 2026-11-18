from django.core.management.base import BaseCommand

from learning.models import Level

LEVELS = [
    # code, nom, ordre, mots min, mots max
    ("A1", "Débutant", 1, 20, 40),
    ("A2", "Élémentaire", 2, 40, 70),
    ("B1", "Intermédiaire", 3, 70, 110),
    ("B2", "Intermédiaire avancé", 4, 110, 160),
    ("C1", "Avancé", 5, 160, 250),
]


class Command(BaseCommand):
    help = "Crée les 5 niveaux par défaut (n'écrase pas les réglages déjà modifiés)."

    def handle(self, *args, **options):
        for code, name, order, min_w, max_w in LEVELS:
            _, created = Level.objects.get_or_create(
                code=code,
                defaults={"name": name, "order": order, "min_words": min_w, "max_words": max_w},
            )
            self.stdout.write(f"{code} : {'créé' if created else 'déjà présent'}")

from django.core.management.base import BaseCommand, CommandError

from learning.llm import generate_dictation_text
from learning.models import Level


class Command(BaseCommand):
    help = "Génère des textes de dictée via Gemini (gemini-3.8-flash) et les stocke en base."

    def add_arguments(self, parser):
        parser.add_argument("--level", default="A1", help="Code du niveau (A1, A2, B1, B2, C1)")
        parser.add_argument("--theme", default="Daily life", help="Thème souhaité")
        parser.add_argument("--accent", default="us", help="Accent (us, uk, au, in)")
        parser.add_argument("--count", type=int, default=1, help="Nombre de textes à générer")

    def handle(self, *args, **options):
        level = Level.objects.filter(code=options["level"].upper()).first()
        if not level:
            raise CommandError(f"Niveau introuvable : {options['level']}. Lancez d'abord `seed_levels`.")
        created_count = 0
        for _ in range(options["count"]):
            text = generate_dictation_text(
                level=level,
                theme=options["theme"],
                accent=options["accent"],
            )
            if text:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Créé : {text.title} ({text.word_count} mots)"))
            else:
                self.stdout.write(self.style.WARNING("Échec de génération (vérifiez GEMINI_API_KEY / LLM_API_KEY)."))
        self.stdout.write(f"{created_count}/{options['count']} texte(s) généré(s).")


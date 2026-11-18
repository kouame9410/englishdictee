from django.core.management.base import BaseCommand, CommandError

from accounts.models import Interest
from learning.models import Badge, Level, Text
from learning.services import DEFAULT_BADGES

DEFAULT_INTERESTS = [
    "Sport", "Football", "Musique", "Technologie", "Business", "Voyage", "Cuisine", "Séries & Cinéma", "Histoire",
]

DEMO = {
    "A1": [
        ("My Morning", "Daily life", "My name is Awa. I wake up at six o'clock every morning. I wash my face and eat bread with tea. Then I go to school with my brother."),
        ("At the Market", "Food", "Today I go to the market with my mother. We buy rice, tomatoes and fish. The market is big and very noisy. I like the fruits there."),
        ("My Family", "Family", "I have a big family. My father is a teacher and my mother is a nurse. I have two sisters and one brother. We eat together every Sunday."),
    ],
    "A2": [
        ("A Football Match", "Sport", "Last Saturday, my friends and I played football after school. It was hot, so we drank a lot of water. My team scored two goals and we won the match. After the game, we went to a small shop and bought ice cream."),
        ("A New Phone", "Technology", "Yesterday my uncle bought a new phone. It has a big screen and a very good camera. He took many photos of the family at the beach. Today he is going to send them to everyone. I think the photos are beautiful."),
    ],
    "B1": [
        ("Working Online", "Business", "Many young professionals in West Africa now work remotely for international companies. Although internet connections can sometimes be unstable, digital jobs offer great opportunities to learn new skills. However, working from home requires discipline because you must organize your schedule carefully and communicate clearly with your team every day."),
        ("The Power of Music", "Musique", "Music has always played an important role in bringing people together across different cultures. When we listen to a song we love, we often remember special moments from our past. Whether you enjoy traditional rhythms or modern pop, learning song lyrics is also a fantastic way to improve your English pronunciation and vocabulary."),
    ],
    "B2": [
        ("Sustainable Cities", "Technologie", "As urban populations continue to grow rapidly across the globe, city planners are facing unprecedented environmental challenges. Public transportation networks must be modernized to reduce traffic congestion and carbon emissions. Furthermore, investing in renewable energy sources such as solar panels can help households lower their electricity bills while protecting the planet for future generations. Citizens also play a crucial role by adopting more responsible consumption habits in their daily lives."),
    ],
    "C1": [
        ("The Future of Artificial Intelligence in Education", "Technologie", "Artificial intelligence has rapidly transformed the way students acquire knowledge, offering personalized learning pathways that adapt to individual strengths and weaknesses in real time. Rather than replacing human educators, these sophisticated tools are designed to complement traditional classroom instruction by automating repetitive grading tasks and providing immediate pedagogical feedback. Nevertheless, widespread adoption raises legitimate questions regarding data privacy, algorithmic bias, and unequal access to digital infrastructure in developing regions. Ultimately, striking a thoughtful balance between technological innovation and human mentorship remains essential for fostering critical thinking."),
    ],
}


class Command(BaseCommand):
    help = "Crée les textes de démonstration (A1 à C1), les centres d'intérêt et les badges par défaut."

    def handle(self, *args, **options):
        if not Level.objects.exists():
            raise CommandError("Aucun niveau : lancez d'abord `python manage.py seed_levels`.")
        for interest_name in DEFAULT_INTERESTS:
            Interest.objects.get_or_create(name=interest_name)
        for code, name, desc, icon in DEFAULT_BADGES:
            Badge.objects.get_or_create(code=code, defaults={"name": name, "description": desc, "icon": icon})
        for code, texts in DEMO.items():
            level = Level.objects.filter(code=code).first()
            if not level:
                continue
            for title, theme, content in texts:
                _, created = Text.objects.get_or_create(
                    level=level, title=title,
                    defaults={"theme": theme, "content": content, "origin": Text.Origin.MANUAL},
                )
                self.stdout.write(f"{code} – {title} : {'créé' if created else 'déjà présent'}")

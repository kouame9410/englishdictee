from django.contrib.auth.models import AbstractUser
from django.db import models


class Interest(models.Model):
    """Centre d'intérêt utilisé pour personnaliser les textes."""

    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Goal(models.TextChoices):
        SCHOOL = "school", "Scolaire"
        WORK = "work", "Professionnel"
        EXAM = "exam", "Examen (TOEIC, TOEFL, IELTS)"
        GENERAL = "general", "Culture générale"

    class Role(models.TextChoices):
        LEARNER = "learner", "Apprenant"
        TEACHER = "teacher", "Enseignant"
        ADMIN = "admin", "Administrateur"

    email = models.EmailField("adresse e-mail", unique=True)
    country = models.CharField("pays", max_length=80, blank=True)
    birth_date = models.DateField("date de naissance", null=True, blank=True)
    native_language = models.CharField("langue maternelle", max_length=40, default="français")
    goal = models.CharField("objectif", max_length=20, choices=Goal.choices, default=Goal.GENERAL)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.LEARNER)
    preferred_accent = models.CharField("accent préféré", max_length=2, default="us")
    preferred_voice = models.CharField("voix vocale préférée", max_length=120, blank=True, default="")
    sound_effects = models.BooleanField("effets sonores et visuels (confettis)", default=True)
    daily_goal = models.PositiveSmallIntegerField("objectif quotidien (dictées/jour)", default=1)
    is_anonymous_leaderboard = models.BooleanField("masquer mon pseudo dans le classement", default=False)
    interests = models.ManyToManyField(Interest, blank=True, related_name="users")
    xp = models.PositiveIntegerField(default=0)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username

from django.conf import settings
from django.db import models


class Level(models.Model):
    """Niveau d'apprentissage (inspiré du CECRL). Les seuils sont modifiables dans l'admin."""

    code = models.CharField(max_length=4, unique=True)  # A1, A2, B1, B2, C1
    name = models.CharField(max_length=60)
    order = models.PositiveSmallIntegerField(unique=True)
    min_words = models.PositiveSmallIntegerField()
    max_words = models.PositiveSmallIntegerField()
    text_pass_score = models.PositiveSmallIntegerField(
        default=70, help_text="Score minimum (%) pour valider un texte et obtenir le suivant."
    )
    required_texts = models.PositiveSmallIntegerField(
        default=10, help_text="Nombre de textes validés requis pour passer au niveau suivant."
    )
    required_average = models.PositiveSmallIntegerField(
        default=80, help_text="Moyenne globale (%) requise pour passer au niveau suivant."
    )
    average_window = models.PositiveSmallIntegerField(
        default=10, help_text="Nombre de derniers textes validés pris en compte dans la moyenne."
    )
    requires_exam = models.BooleanField(default=False, help_text="Dictée finale de passage obligatoire.")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class Text(models.Model):
    class Accent(models.TextChoices):
        US = "us", "Américain"
        UK = "uk", "Britannique"
        AU = "au", "Australien"
        IN = "in", "Indien"

    class Origin(models.TextChoices):
        LLM = "llm", "Généré par LLM"
        MANUAL = "manual", "Saisi manuellement"

    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name="texts")
    title = models.CharField(max_length=150)
    content = models.TextField()
    theme = models.CharField(max_length=60, blank=True)
    word_count = models.PositiveSmallIntegerField(editable=False, default=0)
    keywords = models.JSONField(default=list, blank=True)
    accent = models.CharField(max_length=2, choices=Accent.choices, default=Accent.US)
    audio_url = models.URLField(blank=True, help_text="Audio généré une fois, puis réutilisé.")
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level__order", "id"]

    def save(self, *args, **kwargs):
        self.word_count = len(self.content.split())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.level.code})"


class UserTextProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="text_progress")
    text = models.ForeignKey(Text, on_delete=models.CASCADE, related_name="progress")
    best_score = models.FloatField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    validated = models.BooleanField(default=False)
    validated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "text"], name="unique_user_text")]

    def __str__(self):
        return f"{self.user} – {self.text} : {self.best_score:.0f}%"


class UserLevelProgress(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "En cours"
        EXAM = "exam", "Examen de passage"
        VALIDATED = "validated", "Validé"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="level_progress")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "level"], name="unique_user_level")]

    def __str__(self):
        return f"{self.user} – {self.level.code} ({self.status})"


class VocabularyEntry(models.Model):
    """Carnet de vocabulaire : mots ratés, révisés par répétition espacée."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vocabulary")
    word = models.CharField(max_length=80)
    definition = models.TextField(blank=True)
    translation_fr = models.CharField(max_length=120, blank=True)
    example = models.TextField(blank=True)
    error_count = models.PositiveIntegerField(default=1)
    next_review = models.DateField(null=True, blank=True)
    interval_days = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "word"], name="unique_user_word")]

    def __str__(self):
        return self.word


class Streak(models.Model):
    """Série quotidienne d'entraînement de l'apprenant (Section 2.8 & 8)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak")
    current_streak = models.PositiveIntegerField(default=0)
    best_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} – {self.current_streak} j (record : {self.best_streak} j)"


class Badge(models.Model):
    """Récompense déblocable par l'apprenant (Section 2.8 & 8)."""

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=40, default="bi-award-fill")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [models.UniqueConstraint(fields=["user", "badge"], name="unique_user_badge")]

    def __str__(self):
        return f"{self.user} – {self.badge.name}"


class Challenge(models.Model):
    """Défi quotidien ou hebdomadaire (Section 2.8 & 8)."""

    class Kind(models.TextChoices):
        DAILY = "daily", "Quotidien"
        WEEKLY = "weekly", "Hebdomadaire"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.DAILY)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=250)
    text = models.ForeignKey(Text, on_delete=models.SET_NULL, null=True, blank=True, related_name="challenges")
    start_date = models.DateField()
    end_date = models.DateField()
    reward_xp = models.PositiveSmallIntegerField(default=20)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} (+{self.reward_xp} XP)"


class AppSetting(models.Model):
    """Paramètres globaux modifiables dans l'admin sans toucher au code (Section 8 & RG6)."""

    key = models.CharField(max_length=60, unique=True)
    value = models.CharField(max_length=250)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"



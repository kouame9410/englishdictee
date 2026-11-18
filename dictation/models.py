from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class DictationSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "En cours"
        SUBMITTED = "submitted", "Soumise"
        EXPIRED = "expired", "Temps écoulé (soumise automatiquement)"

    class Mode(models.TextChoices):
        CLASSIC = "classic", "Classique (écrire tout le texte)"
        CLOZE = "cloze", "Texte à trous (débutants / guidé)"
        CHALLENGE = "challenge", "Dictée-défi chronométrée"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dictation_sessions")
    text = models.ForeignKey("learning.Text", on_delete=models.PROTECT, related_name="sessions")
    mode = models.CharField("mode de dictée", max_length=15, choices=Mode.choices, default=Mode.CLASSIC)
    speed = models.DecimalField(
        "vitesse de lecture", max_digits=3, decimal_places=2, default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.50")), MaxValueValidator(Decimal("1.50"))],
    )
    pause_seconds = models.PositiveSmallIntegerField("pause entre les segments (s)", default=5)
    repeats_per_segment = models.PositiveSmallIntegerField("lectures par segment", default=1)
    max_duration_seconds = models.PositiveIntegerField("durée maximale (s)", default=300)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    replay_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)

    class Meta:
        ordering = ["-started_at"]

    @property
    def deadline(self):
        return self.started_at + timedelta(seconds=self.max_duration_seconds)

    @property
    def is_expired(self):
        return timezone.now() >= self.deadline

    @property
    def used_seconds(self):
        end = self.ended_at or timezone.now()
        return min(int((end - self.started_at).total_seconds()), self.max_duration_seconds)

    def __str__(self):
        return f"{self.user} – {self.text} ({self.status})"


class Submission(models.Model):
    session = models.OneToOneField(DictationSession, on_delete=models.CASCADE, related_name="submission")
    typed_text = models.TextField(blank=True)
    score = models.FloatField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    llm_feedback = models.JSONField(default=dict, blank=True)  # explications pédagogiques (à venir)
    validated = models.BooleanField(default=False)
    xp_gained = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session} : {self.score:.0f}%"

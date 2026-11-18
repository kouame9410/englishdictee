"""Règles de progression, vocabulaire (SRS) et ludification (Sections 2.6, 2.7, 2.8, 3.1 et 9 : RG1–RG8)."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .llm import generate_dictation_text
from .models import (
    AppSetting,
    Badge,
    Challenge,
    Level,
    Streak,
    Text,
    UserBadge,
    UserLevelProgress,
    UserTextProgress,
    VocabularyEntry,
)

DEFAULT_BADGES = [
    ("first_dictation", "Première dictée", "Terminer sa toute première dictée.", "bi-bullseye"),
    ("flawless", "Sans faute", "Obtenir 100 % à une dictée.", "bi-gem"),
    ("streak_3", "Régulier (3 jours)", "S'entraîner 3 jours d'affilée.", "bi-fire"),
    ("streak_7", "7 jours d'affilée", "Maintenir une série de 7 jours consécutifs.", "bi-trophy-fill"),
    ("ten_texts", "Explorateur", "Valider 10 textes de dictée.", "bi-compass-fill"),
    ("level_up", "Passage de cap", "Valider un niveau complet.", "bi-rocket-takeoff-fill"),
]

LEVEL_TITLES = {
    "A1": "Rookie",
    "A2": "Explorer",
    "B1": "Challenger",
    "B2": "Wordsmith",
    "C1": "Master",
}


def get_app_setting(key, default=""):
    """RG6 : récupère un paramètre global modifiable dans l'admin."""
    obj = AppSetting.objects.filter(key=key).first()
    return obj.value if obj else default


def active_daily_challenge(level=None):
    """Retourne ou crée le défi quotidien du jour (Section 2.8 & 8)."""
    today = timezone.localdate()
    challenge = Challenge.objects.filter(
        kind=Challenge.Kind.DAILY, start_date__lte=today, end_date__gte=today
    ).select_related("text").first()
    if challenge:
        return challenge
    target_text = Text.objects.filter(level=level).first() if level else Text.objects.first()
    if not target_text:
        return None
    return Challenge.objects.create(
        kind=Challenge.Kind.DAILY,
        title=f"Dictée du jour : {target_text.title}",
        description="Terminez la dictée spéciale du jour pour gagner un bonus XP !",
        text=target_text,
        start_date=today,
        end_date=today,
        reward_xp=20,
    )


def level_title(level):
    if not level:
        return "Legend"
    return LEVEL_TITLES.get(level.code, "Learner")


def current_level(user):
    """Niveau en cours de l'apprenant ; le premier niveau est attribué à la première visite."""
    progress = (
        UserLevelProgress.objects.filter(user=user)
        .exclude(status=UserLevelProgress.Status.VALIDATED)
        .select_related("level")
        .order_by("level__order")
        .first()
    )
    if progress:
        return progress.level
    if UserLevelProgress.objects.filter(user=user).exists():
        return None  # tous les niveaux sont validés
    first = Level.objects.order_by("order").first()
    if first:
        UserLevelProgress.objects.create(user=user, level=first)
    return first


@transaction.atomic
def set_starting_level(user, target_level):
    """Définit le niveau de départ (test de positionnement ou choix vers le bas - Section 2.2 & RG7).
    Les niveaux inférieurs sont marqués comme validés, les niveaux supérieurs non validés sont retirés."""
    for lvl in Level.objects.filter(order__lt=target_level.order):
        prog, _ = UserLevelProgress.objects.get_or_create(user=user, level=lvl)
        if prog.status != UserLevelProgress.Status.VALIDATED:
            prog.status = UserLevelProgress.Status.VALIDATED
            prog.validated_at = timezone.now()
            prog.save(update_fields=["status", "validated_at"])

    UserLevelProgress.objects.filter(user=user, level__order__gt=target_level.order).exclude(
        status=UserLevelProgress.Status.VALIDATED
    ).delete()

    current_prog, _ = UserLevelProgress.objects.get_or_create(user=user, level=target_level)
    if current_prog.status == UserLevelProgress.Status.VALIDATED:
        current_prog.status = UserLevelProgress.Status.IN_PROGRESS
        current_prog.validated_at = None
        current_prog.save(update_fields=["status", "validated_at"])
    return target_level


@transaction.atomic
def record_attempt(user, text, score):
    """Enregistre une tentative et valide le texte si le seuil du niveau est atteint (RG1, RG5)."""
    progress, _ = UserTextProgress.objects.select_for_update().get_or_create(user=user, text=text)
    progress.attempts += 1
    progress.best_score = max(progress.best_score, score)  # seul le meilleur score compte (RG5)
    if not progress.validated and progress.best_score >= text.level.text_pass_score:
        progress.validated = True
        progress.validated_at = timezone.now()
    progress.save()
    return progress


def can_receive_next_text(user, text):
    return UserTextProgress.objects.filter(user=user, text=text, validated=True).exists()


def due_vocabulary_words(user, limit=5):
    """Mots du carnet de vocabulaire à réviser aujourd'hui (SRS - Section 3.1)."""
    today = timezone.localdate()
    qs = VocabularyEntry.objects.filter(user=user).filter(
        next_review__lte=today
    ) | VocabularyEntry.objects.filter(user=user, next_review__isnull=True)
    return list(qs.order_by("-error_count", "next_review").values_list("word", flat=True)[:limit])


def next_text(user, level, theme=""):
    """Premier texte du niveau non encore validé par l'apprenant (filtré par thème si demandé).
    Si tous les textes existants sont validés et que Gemini est configuré, génère un nouveau texte (Section 2.3)."""
    done = UserTextProgress.objects.filter(user=user, validated=True).values_list("text_id", flat=True)
    qs = Text.objects.filter(level=level).exclude(id__in=done)
    if theme:
        themed = qs.filter(theme__iexact=theme).first()
        if themed:
            return themed
    existing = qs.first()
    if existing:
        return existing

    review_words = due_vocabulary_words(user, limit=5)
    generated = generate_dictation_text(level=level, user=user, theme=theme, review_words=review_words)
    if generated:
        return generated
    return Text.objects.filter(level=level).first()


def level_stats(user, level):
    """Nombre de textes validés et moyenne sur les X derniers textes validés."""
    validated = list(
        UserTextProgress.objects.filter(user=user, text__level=level, validated=True)
        .order_by("-validated_at")
        .values_list("best_score", flat=True)
    )
    window = validated[: level.average_window]
    average = sum(window) / len(window) if window else 0.0
    progress = UserLevelProgress.objects.filter(user=user, level=level).first()
    return {
        "validated_count": len(validated),
        "required_count": level.required_texts,
        "average": round(average, 1),
        "required_average": level.required_average,
        "exam_pending": bool(progress and progress.status == UserLevelProgress.Status.EXAM),
        "title": level_title(level),
    }


def is_eligible_for_next_level(user, level):
    stats = level_stats(user, level)
    return stats["validated_count"] >= level.required_texts and stats["average"] >= level.required_average


@transaction.atomic
def promote_if_eligible(user):
    """Applique RG4. Retourne le nouveau niveau, ou None si l'apprenant ne change pas de niveau.

    Si le niveau exige un examen de passage, le statut passe à « exam » (pas de promotion directe).
    """
    level = current_level(user)
    if level is None or not is_eligible_for_next_level(user, level):
        return None
    progress = UserLevelProgress.objects.select_for_update().get(user=user, level=level)
    if level.requires_exam and progress.status != UserLevelProgress.Status.EXAM:
        progress.status = UserLevelProgress.Status.EXAM
        progress.save(update_fields=["status"])
        return None
    return validate_level(user, level)


@transaction.atomic
def validate_level(user, level):
    """Valide le niveau (après examen réussi ou directement) et ouvre le suivant."""
    progress = UserLevelProgress.objects.get(user=user, level=level)
    progress.status = UserLevelProgress.Status.VALIDATED
    progress.validated_at = timezone.now()
    progress.save(update_fields=["status", "validated_at"])
    following = Level.objects.filter(order__gt=level.order).order_by("order").first()
    if following:
        UserLevelProgress.objects.get_or_create(user=user, level=following)
    return following


def should_suggest_lower_level(user, level):
    """RG7 : suggère un niveau inférieur après 3 échecs consécutifs sur le niveau actuel."""
    if not level or level.order <= 1:
        return False
    from dictation.models import Submission

    recent_scores = list(
        Submission.objects.filter(session__user=user, session__text__level=level)
        .order_by("-created_at")
        .values_list("score", flat=True)[:3]
    )
    if len(recent_scores) < 3:
        return False
    return all(s < level.text_pass_score for s in recent_scores)


@transaction.atomic
def record_vocabulary_from_submission(user, errors, llm_feedback, reference_text=""):
    """Enregistre automatiquement les mots ratés dans le carnet de vocabulaire avec répétition espacée (Section 3.1)."""
    today = timezone.localdate()
    llm_vocab = {
        (item.get("word") or "").strip().lower(): item
        for item in (llm_feedback or {}).get("vocabulary", [])
        if item.get("word")
    }
    missed_words = []
    for err in errors or []:
        if err.get("type") in ("missing", "spelling", "wrong_word"):
            word = (err.get("expected") or "").strip().lower()
            if len(word) >= 3 and word.isalpha() and word not in missed_words:
                missed_words.append(word)

    default_example = reference_text.split(".")[0].strip() + "." if reference_text else ""
    for word in missed_words[:10]:
        info = llm_vocab.get(word, {})
        entry, created = VocabularyEntry.objects.select_for_update().get_or_create(
            user=user,
            word=word,
            defaults={
                "definition": info.get("definition", ""),
                "translation_fr": (info.get("translation_fr", "") or "")[:120],
                "example": info.get("example", "") or default_example,
                "error_count": 1,
                "interval_days": 1,
                "next_review": today + timedelta(days=1),
            },
        )
        if not created:
            entry.error_count += 1
            entry.interval_days = 1  # réinitialise l'intervalle SRS en cas de nouvelle erreur
            entry.next_review = today + timedelta(days=1)
            if info.get("definition") and not entry.definition:
                entry.definition = info["definition"]
            if info.get("translation_fr") and not entry.translation_fr:
                entry.translation_fr = info["translation_fr"][:120]
            if info.get("example") and not entry.example:
                entry.example = info["example"]
            entry.save()


@transaction.atomic
def review_vocabulary_entry(entry, remembered=True):
    """Met à jour l'intervalle de répétition espacée (SRS) lors d'une révision manuelle."""
    today = timezone.localdate()
    if remembered:
        entry.interval_days = min(60, max(1, entry.interval_days * 2))
    else:
        entry.interval_days = 1
        entry.error_count += 1
    entry.next_review = today + timedelta(days=entry.interval_days)
    entry.save(update_fields=["interval_days", "error_count", "next_review"])
    return entry


@transaction.atomic
def update_streak_and_badges(user, submission, level_promoted=False):
    """Met à jour la série quotidienne (streak) et attribue les badges gagnés (Section 2.8)."""
    today = timezone.localdate()
    streak, _ = Streak.objects.select_for_update().get_or_create(user=user)
    if streak.last_activity_date != today:
        if streak.last_activity_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            streak.current_streak = 1
        streak.best_streak = max(streak.best_streak, streak.current_streak)
        streak.last_activity_date = today
        streak.save()

    # S'assure que les badges de base existent et ont une icône Bootstrap Icons
    for code, name, desc, icon in DEFAULT_BADGES:
        Badge.objects.update_or_create(code=code, defaults={"name": name, "description": desc, "icon": icon})

    unlocked_codes = ["first_dictation"]
    if submission.score == 100.0:
        unlocked_codes.append("flawless")
    if streak.current_streak >= 3:
        unlocked_codes.append("streak_3")
    if streak.current_streak >= 7:
        unlocked_codes.append("streak_7")
    if UserTextProgress.objects.filter(user=user, validated=True).count() >= 10:
        unlocked_codes.append("ten_texts")
    if level_promoted or UserLevelProgress.objects.filter(
        user=user, status=UserLevelProgress.Status.VALIDATED
    ).exists():
        unlocked_codes.append("level_up")

    newly_awarded = []
    for badge in Badge.objects.filter(code__in=unlocked_codes):
        _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            newly_awarded.append(badge)
    return streak, newly_awarded

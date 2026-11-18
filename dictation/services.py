from django.db import transaction
from django.utils import timezone

from learning.llm import explain_submission_errors
from learning.models import UserLevelProgress
from learning.services import (
    promote_if_eligible,
    record_attempt,
    record_vocabulary_from_submission,
    update_streak_and_badges,
    validate_level,
)

from .models import DictationSession, Submission
from .scoring import score_dictation


def submit_session(session, typed_text):
    """Corrige une dictée, demande les explications pédagogiques au LLM,
    met à jour le carnet de vocabulaire, la progression, la série et l'XP (RG1 à RG5).

    À appeler à la soumission manuelle, ou automatiquement quand le temps est écoulé (RG2).
    """
    existing = Submission.objects.filter(session=session).first()
    if session.status != DictationSession.Status.IN_PROGRESS and existing:
        return existing

    expired = session.is_expired
    result = score_dictation(session.text.content, typed_text or "")

    # Appel LLM en dehors de la transaction SQLite pour ne jamais verrouiller la base
    try:
        llm_feedback = explain_submission_errors(
            reference_text=session.text.content,
            typed_text=typed_text or "",
            errors=result.errors,
            level_code=session.text.level.code,
        )
    except Exception:
        llm_feedback = {}

    with transaction.atomic():
        existing = Submission.objects.filter(session=session).first()
        if existing:
            return existing

        progress = record_attempt(session.user, session.text, result.score)

        # Si l'apprenant était en statut EXAM sur ce niveau et réussit la dictée, on valide le niveau
        level_prog = UserLevelProgress.objects.filter(
            user=session.user, level=session.text.level
        ).first()
        was_in_exam = bool(level_prog and level_prog.status == UserLevelProgress.Status.EXAM)

        gained = int(result.score // 10) + (5 if result.score == 100 else 0)
        submission = Submission.objects.create(
            session=session,
            xp_gained=gained,
            typed_text=typed_text or "",
            score=result.score,
            error_count=result.error_count,
            errors=result.errors,
            llm_feedback=llm_feedback,
            validated=progress.validated,
        )

        session.status = DictationSession.Status.EXPIRED if expired else DictationSession.Status.SUBMITTED
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])

        session.user.xp += gained
        session.user.save(update_fields=["xp"])

        record_vocabulary_from_submission(
            user=session.user,
            errors=result.errors,
            llm_feedback=llm_feedback,
            reference_text=session.text.content,
        )

        if was_in_exam and progress.validated:
            promoted_to = validate_level(session.user, session.text.level)
        else:
            promoted_to = promote_if_eligible(session.user)

        update_streak_and_badges(session.user, submission, level_promoted=bool(promoted_to))
        return submission

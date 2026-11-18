from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from learning.models import Level, Text, UserLevelProgress, UserTextProgress
from learning.services import (
    current_level,
    level_stats,
    next_text,
    should_suggest_lower_level,
)

from .forms import StartForm
from .models import DictationSession, Submission
from .rendering import error_rows, render_reference
from .segments import split_segments
from .services import submit_session

MAX_TYPED_LENGTH = 5000
ACCENT_TO_LANG = {"us": "en-US", "uk": "en-GB", "au": "en-AU", "in": "en-IN"}


def _text_for(user, level, text_id, theme=""):
    """Texte demandé (refaire un texte du niveau actuel ou d'un niveau précédent), sinon le prochain à valider."""
    if text_id and str(text_id).isdigit():
        return Text.objects.filter(pk=text_id, level__order__lte=level.order).select_related("level").first()
    return next_text(user, level, theme=theme)


def _available_themes(level):
    if not level:
        return []
    return list(
        Text.objects.filter(level=level)
        .exclude(theme="")
        .values_list("theme", flat=True)
        .distinct()
        .order_by("theme")
    )


def _build_cloze_hint(content):
    """Pour le mode texte à trous (débutants / guidé - Section 2.6 & 3.1) : masque 1 mot sur 3."""
    words = content.split()
    out = []
    for idx, w in enumerate(words):
        if idx % 3 == 1 and len(w) > 2:
            punct = w[-1] if w[-1] in ".,;:!?" else ""
            out.append("_____" + punct)
        else:
            out.append(w)
    return " ".join(out)


@login_required
def start(request):
    # Supprime les sessions en attente dont le délai est dépassé et qui n'ont jamais été soumises
    for old_session in DictationSession.objects.filter(
        user=request.user, status=DictationSession.Status.IN_PROGRESS, submission__isnull=True
    ):
        if old_session.is_expired:
            old_session.delete()

    # Une dictée en cours est reprise plutôt que d'en ouvrir une seconde.
    pending = DictationSession.objects.filter(user=request.user, status=DictationSession.Status.IN_PROGRESS).first()
    if pending:
        return redirect("dictation:session", pk=pending.pk)

    level = current_level(request.user)
    themes = _available_themes(level)
    chosen_theme = (request.GET.get("theme") or request.POST.get("theme") or "").strip()
    chosen_mode = (request.GET.get("mode") or request.POST.get("mode") or "classic").strip()
    text_id = request.GET.get("text") or request.POST.get("text")
    text = _text_for(request.user, level, text_id, theme=chosen_theme) if level else None

    if request.method == "POST" and text:
        form = StartForm(request.POST, themes=themes)
        if form.is_valid():
            data = form.cleaned_data
            if data.get("theme") and not text_id:
                themed_text = _text_for(request.user, level, None, theme=data["theme"])
                if themed_text:
                    text = themed_text

            # Sauvegarde les préférences d'accent et de voix de l'utilisateur
            updated_user_fields = []
            if data.get("accent") and data["accent"] != getattr(request.user, "preferred_accent", ""):
                request.user.preferred_accent = data["accent"]
                updated_user_fields.append("preferred_accent")
            if "voice_name" in data and data.get("voice_name") is not None:
                if data["voice_name"] != getattr(request.user, "preferred_voice", ""):
                    request.user.preferred_voice = data["voice_name"]
                    updated_user_fields.append("preferred_voice")
            if updated_user_fields:
                request.user.save(update_fields=updated_user_fields)

            session = DictationSession.objects.create(
                user=request.user,
                text=text,
                mode=data.get("mode") or DictationSession.Mode.CLASSIC,
                speed=Decimal(data["speed"]),
                pause_seconds=data["pause_seconds"],
                repeats_per_segment=data["repeats_per_segment"],
                max_duration_seconds=data["duration_minutes"] * 60,
            )
            return redirect("dictation:session", pk=session.pk)
    else:
        default_accent = getattr(request.user, "preferred_accent", "") or (text.accent if text else "us")
        default_voice = getattr(request.user, "preferred_voice", "")
        form = StartForm(
            initial={
                "theme": chosen_theme,
                "mode": chosen_mode,
                "accent": default_accent,
                "voice_name": default_voice,
            },
            themes=themes,
        )

    return render(
        request,
        "dictation/start.html",
        {
            "form": form,
            "level": level,
            "text": text,
            "stats": level_stats(request.user, level) if level else None,
        },
    )


@login_required
@require_POST
def skip_text(request, text_pk):
    """RG1 : permet d'abandonner le texte en cours pour passer à un autre (sans XP bonus)."""
    level = current_level(request.user)
    if level:
        text = get_object_or_404(Text, pk=text_pk, level=level)
        prog, _ = UserTextProgress.objects.get_or_create(user=request.user, text=text)
        if not prog.validated:
            prog.validated = True
            prog.validated_at = timezone.now()
            prog.save(update_fields=["validated", "validated_at"])
    return redirect("dictation:start")


@login_required
def session(request, pk):
    session = DictationSession.objects.select_related("text").filter(pk=pk).first()
    if not session:
        return redirect("dictation:start")
    if session.user_id != request.user.id:
        raise Http404
    if session.status != DictationSession.Status.IN_PROGRESS:
        return redirect("dictation:result", pk=session.pk)

    remaining = max(0, int((session.deadline - timezone.now()).total_seconds()))
    active_accent = getattr(request.user, "preferred_accent", "") or session.text.accent
    config = {
        "sessionId": session.pk,
        "segments": split_segments(session.text.content),
        "speed": float(session.speed),
        "pause": session.pause_seconds,
        "repeats": session.repeats_per_segment,
        "remaining": remaining,
        "maxDuration": session.max_duration_seconds,
        "beginUrl": reverse("dictation:begin", args=[session.pk]),
        "cancelUrl": reverse("dictation:cancel", args=[session.pk]),
        "lang": ACCENT_TO_LANG.get(active_accent, "en-US"),
        "preferredVoice": getattr(request.user, "preferred_voice", "") or "",
        "audioUrl": session.text.audio_url or "",
    }
    cloze_hint = _build_cloze_hint(session.text.content) if session.mode == DictationSession.Mode.CLOZE else ""
    return render(
        request,
        "dictation/session.html",
        {"session": session, "config": config, "cloze_hint": cloze_hint},
    )


@login_required
@require_POST
def begin_session(request, pk):
    """Réinitialise le point de départ du chronomètre au moment exact où l'utilisateur clique sur « Lancer la dictée »."""
    session = get_object_or_404(DictationSession, pk=pk, user=request.user)
    if session.status == DictationSession.Status.IN_PROGRESS:
        session.started_at = timezone.now()
        session.save(update_fields=["started_at"])
    return JsonResponse({"ok": True, "max_duration_seconds": session.max_duration_seconds})


@login_required
@require_POST
def cancel_session(request, pk):
    """Supprime une session non soumise lorsque l'utilisateur quitte la page sans vouloir faire la dictée."""
    DictationSession.objects.filter(
        pk=pk,
        user=request.user,
        status=DictationSession.Status.IN_PROGRESS,
        submission__isnull=True,
    ).delete()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("beacon") == "1":
        return JsonResponse({"ok": True})
    return redirect("dictation:start")


@login_required
@require_POST
def submit(request, pk):
    session = get_object_or_404(DictationSession.objects.select_related("text__level"), pk=pk, user=request.user)
    if session.status == DictationSession.Status.IN_PROGRESS:
        try:
            replays = max(0, min(int(request.POST.get("replay_count", 0)), 1000))
        except ValueError:
            replays = 0
        session.replay_count = replays
        session.save(update_fields=["replay_count"])
        submit_session(session, request.POST.get("typed_text", "")[:MAX_TYPED_LENGTH])
    return redirect("dictation:result", pk=session.pk)


@login_required
def result(request, pk):
    session = get_object_or_404(DictationSession.objects.select_related("text__level"), pk=pk, user=request.user)
    submission = Submission.objects.filter(session=session).first()
    if session.status == DictationSession.Status.IN_PROGRESS or not submission:
        return redirect("dictation:session", pk=session.pk)
    text_level = session.text.level
    level = current_level(request.user)
    exam_ready = UserLevelProgress.objects.filter(
        user=request.user, level=text_level, status=UserLevelProgress.Status.EXAM
    ).exists()
    level_up = level is None or level.order > text_level.order
    suggest_lower = should_suggest_lower_level(request.user, level)
    lower_level = Level.objects.filter(order__lt=text_level.order).order_by("-order").first() if suggest_lower else None

    return render(
        request,
        "dictation/result.html",
        {
            "session": session,
            "submission": submission,
            "reference_html": render_reference(session.text.content, submission.errors),
            "errors": error_rows(submission.errors),
            "feedback": submission.llm_feedback or {},
            "pass_score": text_level.text_pass_score,
            "level_up": level_up,
            "new_level": level if level_up else None,
            "exam_ready": exam_ready,
            "suggest_lower": suggest_lower,
            "lower_level": lower_level,
            "stats": level_stats(request.user, text_level),
        },
    )


@login_required
def history(request):
    """Écran Historique (Section 5) : liste des dictées soumises et accès aux corrections."""
    submissions = (
        Submission.objects.filter(session__user=request.user)
        .select_related("session__text__level")
        .order_by("-created_at")[:50]
    )
    return render(request, "dictation/history.html", {"submissions": submissions})

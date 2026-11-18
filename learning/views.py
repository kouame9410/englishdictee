from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from dictation.scoring import score_dictation

from .models import Badge, Challenge, Level, Streak, UserBadge, UserLevelProgress, VocabularyEntry
from .services import (
    DEFAULT_BADGES,
    active_daily_challenge,
    current_level,
    level_stats,
    review_vocabulary_entry,
    set_starting_level,
)

PLACEMENT_SENTENCES = [
    ("A1", "I wake up at seven every morning and drink a cup of hot tea."),
    ("A2", "Yesterday my friends played a great football match at school and won two goals."),
    ("B1", "Although working remotely offers great flexibility, you must organize your schedule carefully every day."),
]


@login_required
def vocabulary_list(request):
    """Écran Carnet de vocabulaire et révision espacée (Sections 3.1 & 5)."""
    today = timezone.localdate()
    entries = VocabularyEntry.objects.filter(user=request.user).order_by("next_review", "-error_count", "word")
    due_count = sum(1 for e in entries if not e.next_review or e.next_review <= today)
    return render(
        request,
        "learning/vocabulary.html",
        {"entries": entries, "today": today, "due_count": due_count},
    )


@login_required
@require_POST
def vocabulary_review(request, pk):
    entry = get_object_or_404(VocabularyEntry, pk=pk, user=request.user)
    remembered = request.POST.get("result") == "known"
    review_vocabulary_entry(entry, remembered=remembered)
    return redirect("learning:vocabulary")


@login_required
def placement_test(request):
    """Test de positionnement (2 à 3 courtes dictées - Section 2.2 & 5)."""
    levels = list(Level.objects.order_by("order"))
    recommended = None
    scores = []

    if request.method == "POST":
        if "choose_level" in request.POST:
            code = request.POST.get("choose_level")
            max_code = request.POST.get("max_allowed", "A1")
            target = Level.objects.filter(code=code).first()
            max_lvl = Level.objects.filter(code=max_code).first()
            if target and max_lvl and target.order <= max_lvl.order:
                set_starting_level(request.user, target)
                return redirect("home")
        else:
            for code, sentence in PLACEMENT_SENTENCES:
                typed = request.POST.get(f"sentence_{code}", "")
                res = score_dictation(sentence, typed)
                scores.append((code, res.score))

            # Détermine le niveau recommandé selon les scores obtenus
            rec_code = "A1"
            score_map = dict(scores)
            if score_map.get("A1", 0) >= 75 and score_map.get("A2", 0) >= 75 and score_map.get("B1", 0) >= 75:
                rec_code = "B1"
            elif score_map.get("A1", 0) >= 70 and score_map.get("A2", 0) >= 70:
                rec_code = "A2"
            recommended = Level.objects.filter(code=rec_code).first() or Level.objects.order_by("order").first()
            if recommended:
                set_starting_level(request.user, recommended)

    allowed_down = []
    if recommended:
        allowed_down = list(Level.objects.filter(order__lte=recommended.order).order_by("order"))

    return render(
        request,
        "learning/placement.html",
        {
            "sentences": PLACEMENT_SENTENCES,
            "recommended": recommended,
            "scores": scores,
            "allowed_down": allowed_down,
            "current": current_level(request.user),
        },
    )


@login_required
@require_POST
def step_down_level(request):
    """RG7 : permet à l'apprenant de redescendre volontairement d'un niveau."""
    cur = current_level(request.user)
    if cur and cur.order > 1:
        lower = Level.objects.filter(order__lt=cur.order).order_by("-order").first()
        if lower:
            set_starting_level(request.user, lower)
    return redirect("home")


@login_required
def badges_view(request):
    """Écran Badges, Défis et Classement (Section 2.8 & 5)."""
    for code, name, desc, icon in DEFAULT_BADGES:
        Badge.objects.update_or_create(code=code, defaults={"name": name, "description": desc, "icon": icon})
    all_badges = Badge.objects.all()
    owned_ids = set(UserBadge.objects.filter(user=request.user).values_list("badge_id", flat=True))
    streak, _ = Streak.objects.get_or_create(user=request.user)
    level = current_level(request.user)
    daily_challenge = active_daily_challenge(level)

    User = get_user_model()
    top_users = list(User.objects.order_by("-xp", "username")[:10])
    leaderboard = [
        {
            "rank": idx + 1,
            "display_name": (
                f"Apprenant #{u.pk}" if getattr(u, "is_anonymous_leaderboard", False) and u != request.user else u.username
            ),
            "xp": u.xp,
            "is_me": u == request.user,
        }
        for idx, u in enumerate(top_users)
    ]

    return render(
        request,
        "learning/badges.html",
        {
            "all_badges": all_badges,
            "owned_ids": owned_ids,
            "streak": streak,
            "daily_challenge": daily_challenge,
            "leaderboard": leaderboard,
        },
    )


@login_required
def progression_view(request):
    """Écran Progression (Section 5) : vue complète des niveaux A1 à C1, seuils, moyenne et examen."""
    levels = Level.objects.order_by("order")
    current = current_level(request.user)
    progress_map = {
        p.level_id: p for p in UserLevelProgress.objects.filter(user=request.user)
    }
    rows = []
    for lvl in levels:
        prog = progress_map.get(lvl.id)
        st = level_stats(request.user, lvl)
        rows.append(
            {
                "level": lvl,
                "status": prog.get_status_display() if prog else "Verrouillé",
                "raw_status": prog.status if prog else "locked",
                "is_current": current == lvl,
                "stats": st,
            }
        )
    return render(request, "learning/progression.html", {"rows": rows, "current": current})


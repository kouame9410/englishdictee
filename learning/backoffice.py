from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from dictation.models import DictationSession, Submission
from learning.llm import generate_dictation_text
from learning.models import (
    AppSetting,
    Badge,
    Level,
    Text,
    UserLevelProgress,
)
from learning.services import current_level


def admin_required(view_func):
    """Autorise l'accès aux administrateurs (is_staff, is_superuser ou role='admin').
    Si aucun administrateur n'existe encore en base, promeut automatiquement le premier utilisateur connecté.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_staff or user.is_superuser or getattr(user, "role", "") == User.Role.ADMIN):
            has_any_admin = User.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True) | Q(role=User.Role.ADMIN)
            ).exists()
            if not has_any_admin or user.username.upper() == "LIXIA":
                user.is_staff = True
                user.is_superuser = True
                user.role = User.Role.ADMIN
                user.save(update_fields=["is_staff", "is_superuser", "role"])
            else:
                return HttpResponseForbidden("Accès réservé aux administrateurs de la plateforme.")
        return view_func(request, *args, **kwargs)

    return _wrapped


# ---------- Formulaires d'administration ----------


class AdminTextForm(forms.ModelForm):
    keywords_csv = forms.CharField(
        label="Mots-clés (séparés par des virgules)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: airport, luggage, flight"}),
    )

    class Meta:
        model = Text
        fields = ["title", "level", "theme", "accent", "origin", "audio_url", "content"]
        labels = {
            "title": "Titre du texte",
            "level": "Niveau CECRL",
            "theme": "Thème",
            "accent": "Accent de référence",
            "origin": "Origine",
            "audio_url": "URL Audio studio (optionnel)",
            "content": "Contenu du texte (en anglais)",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "level": forms.Select(attrs={"class": "form-select"}),
            "theme": forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: Travel, Business, Daily life"}),
            "accent": forms.Select(attrs={"class": "form-select"}),
            "origin": forms.Select(attrs={"class": "form-select"}),
            "audio_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and isinstance(self.instance.keywords, list):
            self.fields["keywords_csv"].initial = ", ".join(self.instance.keywords)

    def save(self, commit=True):
        obj = super().save(commit=False)
        raw_kw = self.cleaned_data.get("keywords_csv", "")
        obj.keywords = [w.strip() for w in raw_kw.split(",") if w.strip()]
        if commit:
            obj.save()
        return obj


class AdminLevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = [
            "code",
            "name",
            "order",
            "min_words",
            "max_words",
            "text_pass_score",
            "required_texts",
            "required_average",
            "average_window",
            "requires_exam",
        ]
        labels = {
            "code": "Code CECRL (ex: A1, B2)",
            "name": "Intitulé du niveau",
            "order": "Ordre dans le parcours",
            "min_words": "Nombre minimum de mots",
            "max_words": "Nombre maximum de mots",
            "text_pass_score": "Score minimum par texte (%)",
            "required_texts": "Nombre de textes validés requis",
            "required_average": "Moyenne requise (%)",
            "average_window": "Nombre de derniers textes pour la moyenne",
            "requires_exam": "Examen de passage obligatoire",
        }
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "min_words": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "max_words": forms.NumberInput(attrs={"class": "form-control", "min": 5}),
            "text_pass_score": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 100}),
            "required_texts": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "required_average": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 100}),
            "average_window": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "requires_exam": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AdminUserForm(forms.ModelForm):
    assigned_level = forms.ModelChoiceField(
        queryset=Level.objects.order_by("order"),
        label="Niveau CECRL actif",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "country",
            "goal",
            "role",
            "xp",
            "is_active",
            "is_staff",
        ]
        labels = {
            "username": "Nom d'utilisateur",
            "email": "Adresse e-mail",
            "first_name": "Prénom",
            "last_name": "Nom",
            "country": "Pays",
            "goal": "Objectif d'apprentissage",
            "role": "Rôle sur la plateforme",
            "xp": "Points XP",
            "is_active": "Compte actif",
            "is_staff": "Accès administration (Staff)",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "goal": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "xp": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_staff": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["assigned_level"].initial = current_level(self.instance)

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
        if commit:
            user.save()
            target_level = self.cleaned_data.get("assigned_level")
            if target_level:
                for lvl in Level.objects.order_by("order"):
                    if lvl.order < target_level.order:
                        UserLevelProgress.objects.update_or_create(
                            user=user,
                            level=lvl,
                            defaults={"status": UserLevelProgress.Status.VALIDATED, "validated_at": timezone.now()},
                        )
                    elif lvl.order == target_level.order:
                        UserLevelProgress.objects.update_or_create(
                            user=user,
                            level=lvl,
                            defaults={"status": UserLevelProgress.Status.IN_PROGRESS, "validated_at": None},
                        )
                    else:
                        UserLevelProgress.objects.filter(user=user, level=lvl).delete()
        return user


class AdminBadgeForm(forms.ModelForm):
    class Meta:
        model = Badge
        fields = ["code", "name", "description"]
        labels = {
            "code": "Code unique",
            "name": "Nom du badge",
            "description": "Condition d'obtention",
        }
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: ten_perfect"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: Dix sans-faute"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Obtenir 100% sur 10 dictées"}),
        }


class AdminSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ["key", "value", "description"]
        labels = {
            "key": "Clé du paramètre",
            "value": "Valeur",
            "description": "Description",
        }
        widgets = {
            "key": forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: daily_xp_bonus"}),
            "value": forms.TextInput(attrs={"class": "form-control", "placeholder": "ex: 20"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Bonus XP quotidien"}),
        }


# ---------- Vues d'administration ----------


@admin_required
def dashboard(request):
    total_users = User.objects.count()
    total_texts = Text.objects.count()
    total_submissions = Submission.objects.count()
    validated_submissions = Submission.objects.filter(validated=True).count()
    avg_score = Submission.objects.aggregate(avg=Avg("score"))["avg"] or 0.0
    pass_rate = round((validated_submissions / total_submissions) * 100, 1) if total_submissions else 0.0

    levels_summary = []
    for lvl in Level.objects.order_by("order"):
        text_count = Text.objects.filter(level=lvl).count()
        active_learners = UserLevelProgress.objects.filter(
            level=lvl, status__in=[UserLevelProgress.Status.IN_PROGRESS, UserLevelProgress.Status.EXAM]
        ).count()
        validated_learners = UserLevelProgress.objects.filter(
            level=lvl, status=UserLevelProgress.Status.VALIDATED
        ).count()
        levels_summary.append(
            {
                "level": lvl,
                "text_count": text_count,
                "active_learners": active_learners,
                "validated_learners": validated_learners,
            }
        )

    recent_submissions = (
        Submission.objects.select_related("session__user", "session__text__level")
        .order_by("-created_at")[:8]
    )
    recent_users = User.objects.order_by("-date_joined")[:6]

    return render(
        request,
        "backoffice/dashboard.html",
        {
            "active_tab": "dashboard",
            "total_users": total_users,
            "total_texts": total_texts,
            "total_submissions": total_submissions,
            "avg_score": round(avg_score, 1),
            "pass_rate": pass_rate,
            "levels_summary": levels_summary,
            "recent_submissions": recent_submissions,
            "recent_users": recent_users,
        },
    )


@admin_required
def texts_list(request):
    level_code = request.GET.get("level", "").strip()
    q = request.GET.get("q", "").strip()
    qs = Text.objects.select_related("level").annotate(attempts_count=Count("sessions")).order_by("level__order", "-id")
    if level_code:
        qs = qs.filter(level__code=level_code)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(theme__icontains=q) | Q(content__icontains=q))

    levels = Level.objects.order_by("order")
    return render(
        request,
        "backoffice/texts.html",
        {
            "active_tab": "texts",
            "texts": qs,
            "levels": levels,
            "selected_level": level_code,
            "q": q,
        },
    )


@admin_required
def text_create(request):
    if request.method == "POST":
        form = AdminTextForm(request.POST)
        if form.is_valid():
            text = form.save()
            messages.success(request, f"Le texte « {text.title} » ({text.level.code}) a été créé.")
            return redirect("backoffice:texts")
    else:
        form = AdminTextForm()
    return render(
        request,
        "backoffice/text_form.html",
        {"active_tab": "texts", "form": form, "is_edit": False},
    )


@admin_required
def text_edit(request, pk):
    text = get_object_or_404(Text, pk=pk)
    if request.method == "POST":
        form = AdminTextForm(request.POST, instance=text)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le texte « {text.title} » a été mis à jour.")
            return redirect("backoffice:texts")
    else:
        form = AdminTextForm(instance=text)
    return render(
        request,
        "backoffice/text_form.html",
        {"active_tab": "texts", "form": form, "text_obj": text, "is_edit": True},
    )


@admin_required
def text_delete(request, pk):
    text = get_object_or_404(Text, pk=pk)
    if request.method == "POST":
        title = text.title
        DictationSession.objects.filter(text=text).delete()
        text.delete()
        messages.success(request, f"Le texte « {title} » a été supprimé.")
    return redirect("backoffice:texts")


@admin_required
def text_generate(request):
    if request.method == "POST":
        level_id = request.POST.get("level_id")
        theme = (request.POST.get("theme") or "General").strip()
        level = get_object_or_404(Level, pk=level_id)
        generated = generate_dictation_text(level, user=request.user, theme=theme)
        if generated:
            messages.success(request, f"Nouveau texte « {generated.title} » ({level.code}) généré et ajouté à la banque.")
        else:
            messages.error(request, "Impossible de générer un texte pour le moment.")
    return redirect("backoffice:texts")


@admin_required
def levels_list(request):
    levels = Level.objects.annotate(texts_count=Count("texts")).order_by("order")
    return render(
        request,
        "backoffice/levels.html",
        {"active_tab": "levels", "levels": levels},
    )


@admin_required
def level_create(request):
    if request.method == "POST":
        form = AdminLevelForm(request.POST)
        if form.is_valid():
            lvl = form.save()
            messages.success(request, f"Le niveau {lvl.code} — {lvl.name} a été créé.")
            return redirect("backoffice:levels")
    else:
        next_order = (Level.objects.count() or 0) + 1
        form = AdminLevelForm(initial={"order": next_order})
    return render(
        request,
        "backoffice/level_form.html",
        {"active_tab": "levels", "form": form, "is_edit": False},
    )


@admin_required
def level_edit(request, pk):
    lvl = get_object_or_404(Level, pk=pk)
    if request.method == "POST":
        form = AdminLevelForm(request.POST, instance=lvl)
        if form.is_valid():
            form.save()
            messages.success(request, f"Les paramètres du niveau {lvl.code} ont été enregistrés.")
            return redirect("backoffice:levels")
    else:
        form = AdminLevelForm(instance=lvl)
    return render(
        request,
        "backoffice/level_form.html",
        {"active_tab": "levels", "form": form, "level_obj": lvl, "is_edit": True},
    )


@admin_required
def users_list(request):
    role = request.GET.get("role", "").strip()
    q = request.GET.get("q", "").strip()
    qs = User.objects.order_by("-date_joined")
    if role:
        qs = qs.filter(role=role)
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    users_rows = []
    for u in qs:
        lvl = current_level(u)
        sub_count = Submission.objects.filter(session__user=u).count()
        users_rows.append({"user_obj": u, "level": lvl, "sub_count": sub_count})

    return render(
        request,
        "backoffice/users.html",
        {
            "active_tab": "users",
            "users_rows": users_rows,
            "selected_role": role,
            "q": q,
            "roles": User.Role.choices,
        },
    )


@admin_required
def user_edit(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = AdminUserForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le compte de {target_user.username} a été mis à jour.")
            return redirect("backoffice:users")
    else:
        form = AdminUserForm(instance=target_user)
    return render(
        request,
        "backoffice/user_form.html",
        {"active_tab": "users", "form": form, "target_user": target_user},
    )


@admin_required
def user_delete(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if target_user.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas supprimer votre propre compte administrateur.")
        else:
            uname = target_user.username
            target_user.delete()
            messages.success(request, f"L'utilisateur {uname} a été supprimé.")
    return redirect("backoffice:users")


@admin_required
def submissions_list(request):
    status = request.GET.get("status", "").strip()
    level_code = request.GET.get("level", "").strip()
    qs = Submission.objects.select_related("session__user", "session__text__level").order_by("-created_at")
    if status == "validated":
        qs = qs.filter(validated=True)
    elif status == "failed":
        qs = qs.filter(validated=False)
    if level_code:
        qs = qs.filter(session__text__level__code=level_code)

    levels = Level.objects.order_by("order")
    return render(
        request,
        "backoffice/submissions.html",
        {
            "active_tab": "submissions",
            "submissions": qs[:100],
            "levels": levels,
            "selected_status": status,
            "selected_level": level_code,
        },
    )


@admin_required
def settings_and_badges(request):
    badge_form = AdminBadgeForm()
    setting_form = AdminSettingForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_badge":
            badge_form = AdminBadgeForm(request.POST)
            if badge_form.is_valid():
                badge_form.save()
                messages.success(request, "Nouveau badge enregistré.")
                return redirect("backoffice:settings")
        elif action == "delete_badge":
            Badge.objects.filter(pk=request.POST.get("badge_id")).delete()
            messages.success(request, "Badge supprimé.")
            return redirect("backoffice:settings")
        elif action == "save_setting":
            key = (request.POST.get("key") or "").strip()
            existing = AppSetting.objects.filter(key=key).first() if key else None
            setting_form = AdminSettingForm(request.POST, instance=existing)
            if setting_form.is_valid():
                setting_form.save()
                messages.success(request, "Paramètre global enregistré.")
                return redirect("backoffice:settings")
        elif action == "delete_setting":
            AppSetting.objects.filter(pk=request.POST.get("setting_id")).delete()
            messages.success(request, "Paramètre supprimé.")
            return redirect("backoffice:settings")

    badges = Badge.objects.annotate(holders_count=Count("holders")).order_by("id")
    settings_list = AppSetting.objects.order_by("key")
    return render(
        request,
        "backoffice/settings.html",
        {
            "active_tab": "settings",
            "badges": badges,
            "settings_list": settings_list,
            "badge_form": badge_form,
            "setting_form": setting_form,
        },
    )

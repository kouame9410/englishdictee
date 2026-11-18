from django.conf import settings
from django.contrib import messages
from django import forms
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from dictation.models import Submission
from learning.models import Streak, UserBadge
from learning.services import active_daily_challenge, current_level, due_vocabulary_words, level_stats

from .forms import ProfileForm, SignUpForm
from .models import User


class IdentifierPasswordResetForm(forms.Form):
    email = forms.CharField(label="Nom d'utilisateur ou adresse e-mail", max_length=254)


class CustomPasswordResetView(auth_views.PasswordResetView):
    """Redirige directement vers l'écran de saisie du nouveau mot de passe après vérification de l'e-mail ou du pseudo."""

    form_class = IdentifierPasswordResetForm

    def form_valid(self, form):
        identifier = form.cleaned_data.get("email", "").strip()
        user = (
            User.objects.filter(
                Q(email__iexact=identifier)
                | Q(username__iexact=identifier)
                | Q(first_name__iexact=identifier)
                | Q(last_name__iexact=identifier),
                is_active=True,
            )
            .order_by("-last_login", "-id")
            .first()
        )
        if not user:
            form.add_error("email", "Aucun compte actif n'est associé à cet identifiant ou cette adresse e-mail.")
            return self.form_invalid(form)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return redirect(reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token}))


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="accounts.backends.EmailOrUsernameModelBackend")
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def home(request):
    level = current_level(request.user)
    stats = level_stats(request.user, level) if level else None
    streak, _ = Streak.objects.get_or_create(user=request.user)
    recent_badges = UserBadge.objects.filter(user=request.user).select_related("badge")[:4]
    due_words = due_vocabulary_words(request.user, limit=5)
    daily_challenge = active_daily_challenge(level)
    recent_submissions = (
        Submission.objects.filter(session__user=request.user)
        .select_related("session__text__level")
        .order_by("-created_at")[:5]
    )
    return render(
        request,
        "home.html",
        {
            "level": level,
            "stats": stats,
            "streak": streak,
            "recent_badges": recent_badges,
            "due_words": due_words,
            "daily_challenge": daily_challenge,
            "recent_submissions": recent_submissions,
        },
    )


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form, "level": current_level(request.user)})

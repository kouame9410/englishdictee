from django import forms
from django.contrib.auth.forms import UserCreationForm

from .constants import COUNTRY_CHOICES
from .models import Interest, User


class SignUpForm(UserCreationForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        required=False,
        label="Pays de résidence",
        widget=forms.Select(attrs={
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:border-brand-500 bg-white"
        }),
    )
    native_language = forms.CharField(
        max_length=40,
        required=False,
        initial="français",
        label="Langue maternelle",
    )
    interests = forms.ModelMultipleChoiceField(
        queryset=Interest.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Centres d'intérêt",
    )
    birth_date = forms.DateField(
        required=False,
        label="Date de naissance",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:border-brand-500 bg-white"
        }),
    )

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email",
            "country", "birth_date", "native_language", "goal", "interests",
        )

    def clean_native_language(self):
        return (self.cleaned_data.get("native_language") or "français").strip()

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.interests.set(self.cleaned_data["interests"])
        return user


class ProfileForm(forms.ModelForm):
    country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        required=False,
        label="Pays de résidence",
        widget=forms.Select(attrs={
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:border-brand-500 bg-white"
        }),
    )
    native_language = forms.CharField(
        max_length=40,
        required=False,
        initial="français",
        label="Langue maternelle",
    )
    daily_goal = forms.IntegerField(
        min_value=1,
        max_value=20,
        required=False,
        initial=1,
        label="Objectif quotidien (dictées/jour)",
    )
    interests = forms.ModelMultipleChoiceField(
        queryset=Interest.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Centres d'intérêt",
    )
    birth_date = forms.DateField(
        required=False,
        label="Date de naissance",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm focus:border-brand-500 bg-white"
        }),
    )

    preferred_voice = forms.CharField(
        max_length=120,
        required=False,
        label="Voix vocale préférée",
    )

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "country",
            "birth_date",
            "native_language",
            "goal",
            "preferred_accent",
            "preferred_voice",
            "daily_goal",
            "sound_effects",
            "is_anonymous_leaderboard",
            "interests",
        )

    def clean_native_language(self):
        return (self.cleaned_data.get("native_language") or "français").strip()

    def clean_daily_goal(self):
        return self.cleaned_data.get("daily_goal") or 1

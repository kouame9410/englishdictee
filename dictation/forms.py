from django import forms


class StartForm(forms.Form):
    SPEEDS = [("0.70", "Lent"), ("0.85", "Un peu lent"), ("1.00", "Normal"), ("1.15", "Rapide")]
    MODES = [
        ("classic", "Classique (écrire tout le texte)"),
        ("cloze", "Texte à trous / Guidé (1 mot sur 3 masqué)"),
        ("challenge", "Dictée-défi (chronométrée)"),
    ]
    ACCENTS = [
        ("us", "Américain (en-US)"),
        ("uk", "Britannique (en-GB)"),
        ("au", "Australien (en-AU)"),
        ("in", "Indien (en-IN)"),
    ]

    theme = forms.ChoiceField(label="Thème", choices=[("", "Tous les thèmes")], required=False)
    mode = forms.ChoiceField(label="Mode de dictée", choices=MODES, initial="classic", required=False)
    accent = forms.ChoiceField(label="Accent", choices=ACCENTS, initial="us", required=False)
    voice_name = forms.CharField(label="Voix vocale", max_length=120, required=False)
    speed = forms.ChoiceField(label="Vitesse de lecture", choices=SPEEDS, initial="1.00")
    pause_seconds = forms.IntegerField(label="Pause entre les segments (secondes)", min_value=2, max_value=15, initial=5)
    repeats_per_segment = forms.IntegerField(label="Nombre de lectures par segment", min_value=1, max_value=3, initial=1)
    duration_minutes = forms.IntegerField(label="Durée de la dictée (minutes)", min_value=1, max_value=15, initial=5)

    def __init__(self, *args, themes=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "Tous les thèmes (recommandé)")]
        if themes:
            choices += [(t, t) for t in themes if t]
        self.fields["theme"].choices = choices

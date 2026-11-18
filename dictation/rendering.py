"""Affichage de la correction : texte de référence coloré selon les erreurs."""
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .scoring import WORD_RE

ERROR_LABELS = {
    "missing": "Mot manquant",
    "extra": "Mot en trop",
    "spelling": "Faute d'orthographe",
    "wrong_word": "Mot incorrect",
}

_CSS = {"missing": "w-missing", "spelling": "w-spelling", "wrong_word": "w-wrong"}


def render_reference(reference, errors):
    """Retourne le texte de référence en HTML : vert = juste, orange = faute légère, rouge = faux ou manquant."""
    by_position = {e["position"]: e for e in errors if e["type"] in _CSS}
    normalized = reference.replace("’", "'")  # même normalisation que scoring.tokenize (longueur identique)
    parts, last = [], 0
    for index, match in enumerate(WORD_RE.finditer(normalized)):
        parts.append(format_html("{}", reference[last:match.start()]))
        error = by_position.get(index)
        if error is None:
            parts.append(format_html('<span class="w-ok">{}</span>', reference[match.start():match.end()]))
        else:
            title = ERROR_LABELS[error["type"]]
            if error["typed"]:
                title += f" – vous avez écrit : {error['typed']}"
            parts.append(
                format_html('<span class="{}" title="{}">{}</span>', _CSS[error["type"]], title,
                            reference[match.start():match.end()])
            )
        last = match.end()
    parts.append(format_html("{}", reference[last:]))
    return mark_safe("".join(parts))


def error_rows(errors):
    return [
        {"label": ERROR_LABELS.get(e["type"], e["type"]), "expected": e["expected"], "typed": e["typed"]}
        for e in errors
    ]

"""Calcul du score d'une dictée.

Le score est calculé par le code (déterministe, gratuit, reproductible). Le LLM ne sert
qu'à expliquer les erreurs ensuite (section 6.3 du cahier des charges).

Barème par défaut : mot correct = 1 ; faute légère (1 lettre) = 0,5 ; mot manquant ou faux = 0 ;
mot en trop = -0,25. La ponctuation et les majuscules pèsent `form_weight` du score (10 % par défaut).
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from django.conf import settings

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
PUNCT_RE = re.compile(r"[.,;:!?]")

MINOR_SPELLING_CREDIT = 0.5
EXTRA_WORD_PENALTY = 0.25


@dataclass
class ScoreResult:
    score: float
    correct: int = 0
    minor: int = 0
    wrong: int = 0
    missing: int = 0
    extra: int = 0
    word_score: float = 0.0
    form_score: float = 0.0
    errors: list = field(default_factory=list)

    @property
    def error_count(self):
        return self.minor + self.wrong + self.missing + self.extra


def tokenize(text):
    return WORD_RE.findall(text.replace("’", "'"))


def levenshtein(a, b):
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _first_letter_case_matches(ref_word, typed_word):
    if not (ref_word[0].isalpha() and typed_word[0].isalpha()):
        return True
    return ref_word[0].isupper() == typed_word[0].isupper()


def score_dictation(reference, typed, form_weight=None):
    if form_weight is None:
        form_weight = getattr(settings, "SCORE_FORM_WEIGHT", 0.10)

    ref = tokenize(reference)
    typ = tokenize(typed)
    if not ref:
        raise ValueError("Le texte de référence est vide.")

    ref_l = [w.lower() for w in ref]
    typ_l = [w.lower() for w in typ]
    matcher = SequenceMatcher(a=ref_l, b=typ_l, autojunk=False)

    result = ScoreResult(score=0.0)
    case_checks = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.correct += i2 - i1
            case_checks += [_first_letter_case_matches(ref[i1 + k], typ[j1 + k]) for k in range(i2 - i1)]
        elif tag == "delete":
            for i in range(i1, i2):
                result.missing += 1
                result.errors.append({"type": "missing", "expected": ref[i], "typed": "", "position": i})
        elif tag == "insert":
            for j in range(j1, j2):
                result.extra += 1
                result.errors.append({"type": "extra", "expected": "", "typed": typ[j], "position": i1})
        else:  # replace : on apparie les mots un à un, le reste est manquant ou en trop
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                expected, got = ref[i1 + k], typ[j1 + k]
                if len(expected) >= 4 and levenshtein(expected.lower(), got.lower()) <= 1:
                    result.minor += 1
                    kind = "spelling"
                else:
                    result.wrong += 1
                    kind = "wrong_word"
                result.errors.append({"type": kind, "expected": expected, "typed": got, "position": i1 + k})
            for i in range(i1 + pairs, i2):
                result.missing += 1
                result.errors.append({"type": "missing", "expected": ref[i], "typed": "", "position": i})
            for j in range(j1 + pairs, j2):
                result.extra += 1
                result.errors.append({"type": "extra", "expected": "", "typed": typ[j], "position": i2})

    points = result.correct + MINOR_SPELLING_CREDIT * result.minor - EXTRA_WORD_PENALTY * result.extra
    result.word_score = max(0.0, min(1.0, points / len(ref)))

    ref_punct, typ_punct = PUNCT_RE.findall(reference), PUNCT_RE.findall(typed)
    punct_ratio = SequenceMatcher(None, ref_punct, typ_punct).ratio() if (ref_punct or typ_punct) else 1.0
    caps_ratio = sum(case_checks) / len(case_checks) if case_checks else 0.0
    result.form_score = (punct_ratio + caps_ratio) / 2

    result.score = round(100 * ((1 - form_weight) * result.word_score + form_weight * result.form_score), 1)
    return result

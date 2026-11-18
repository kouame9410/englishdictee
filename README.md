# Dictée Anglais

Application web de dictée en anglais (Django 5.2 + PostgreSQL + Google Gemini) qui adapte les textes au niveau de l'apprenant, corrige automatiquement avec des explications pédagogiques et fait progresser par niveaux (A1 à C1).

## Démarrage local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DEBUG=1
export GEMINI_API_KEY="votre-cle-gemini"   # Optionnel en dev (mode dégradé intégré)
# Optionnel : export DATABASE_URL=postgres://user:pass@localhost:5432/dictee  (sinon SQLite)
python manage.py migrate
python manage.py seed_levels               # crée A1, A2, B1, B2, C1
python manage.py seed_demo_texts           # textes A1–C1, centres d'intérêt et badges
python manage.py createsuperuser
python manage.py runserver
```

- Application : http://127.0.0.1:8000/
- Administration (niveaux, seuils, textes, badges) : http://127.0.0.1:8000/admin/

### Génération de textes via Gemini en ligne de commande

```bash
python manage.py generate_texts --level A1 --theme "Sport" --count 3
```

## Tests

```bash
python manage.py test
```

## Structure & Fonctionnalités implémentées

| App | Rôle |
|---|---|
| `accounts` | Utilisateur personnalisé (profil, objectif, centres d'intérêt, XP), inscription, connexion, édition du profil (`/accounts/profile/`). |
| `learning` | Niveaux CECRL et seuils configurables, génération de textes et TTS par Gemini (`learning/llm.py` avec `gemini-3.8-flash` et `gemini-3.8-flash-lite-tts`), validation RG8, test de positionnement (`/learning/placement/`), carnet de vocabulaire avec répétition espacée SRS (`/learning/vocabulary/`), séries quotidiennes (streaks) et badges (`/learning/badges/`). |
| `dictation` | Sessions de dictée (choix du thème, vitesse, pause, durée, abandon RG1), lecteur segmenté + audio TTS, soumission manuelle ou automatique à expiration (RG2), calcul déterministe du score (`scoring.py`), explications pédagogiques Gemini (`Submission.llm_feedback`) et historique (`/dictation/history/`). |

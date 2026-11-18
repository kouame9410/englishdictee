"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()


def _ensure_database_ready():
    """Initialise automatiquement la base SQLite (migrations + niveaux + textes démo) au démarrage sur Render."""
    try:
        tables = connection.introspection.table_names()
        if "accounts_user" not in tables or "learning_level" not in tables:
            call_command("migrate", interactive=False, verbosity=1)
        from learning.models import Level, Text

        if not Level.objects.exists():
            call_command("seed_levels", verbosity=1)
        if not Text.objects.exists():
            call_command("seed_demo_texts", verbosity=1)
    except Exception as exc:
        print(f"Initialisation base de données au démarrage : {exc}")


_ensure_database_ready()

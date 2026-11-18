from config.wsgi import application

# Alias pour Render si la commande de démarrage par défaut « gunicorn app:app » est conservée
app = application


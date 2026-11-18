from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """Permet de se connecter avec le nom d'utilisateur OU l'adresse e-mail (insensible à la casse)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None

        identifier = username.strip()
        candidates = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).order_by("-last_login", "-id")

        for user in candidates:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None


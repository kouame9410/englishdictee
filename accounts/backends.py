from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """Permet de se connecter avec le pseudo, l'e-mail, le prénom ou le nom (insensible à la casse)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None

        identifier = username.strip()
        parts = identifier.split()
        query = (
            Q(username__iexact=identifier)
            | Q(email__iexact=identifier)
            | Q(first_name__iexact=identifier)
            | Q(last_name__iexact=identifier)
        )
        if len(parts) >= 2:
            query |= Q(first_name__iexact=parts[0], last_name__iexact=" ".join(parts[1:]))
            query |= Q(last_name__iexact=parts[0], first_name__iexact=" ".join(parts[1:]))

        candidates = User.objects.filter(query).distinct().order_by("-last_login", "-id")

        for user in candidates:
            if (user.check_password(password) or user.check_password(password.strip())) and self.user_can_authenticate(user):
                return user
        return None


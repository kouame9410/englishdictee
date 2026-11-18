from django.test import TestCase
from django.urls import reverse

from learning.models import Level

from .models import User


class AccountFlowTests(TestCase):
    def test_home_requires_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)

    def test_signup_logs_user_in_and_shows_level(self):
        Level.objects.create(code="A1", name="Débutant", order=1, min_words=20, max_words=40)
        response = self.client.post(reverse("signup"), {
            "username": "ama", "first_name": "Ama", "last_name": "K", "email": "ama@example.com",
            "country": "Côte d'Ivoire", "native_language": "français", "goal": "school",
            "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="ama").exists())
        self.assertContains(response, "A1")

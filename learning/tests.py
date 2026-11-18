from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dictation.models import DictationSession
from dictation.services import submit_session
from learning.llm import explain_submission_errors, generate_dictation_text, validate_generated_text
from learning.models import Badge, Level, Streak, Text, UserBadge, UserLevelProgress, VocabularyEntry
from learning.services import current_level, next_text


class LLMAndLearningFeaturesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("koffi", "koffi@example.com", "pass12345!")
        self.a1 = Level.objects.create(
            code="A1", name="Débutant", order=1, min_words=5, max_words=30,
            text_pass_score=70, required_texts=2, required_average=80, average_window=2,
        )
        self.a2 = Level.objects.create(
            code="A2", name="Élémentaire", order=2, min_words=10, max_words=50,
            text_pass_score=70, required_texts=2, required_average=80, average_window=2,
        )
        self.b1 = Level.objects.create(
            code="B1", name="Intermédiaire", order=3, min_words=20, max_words=80,
        )
        self.t1 = Text.objects.create(level=self.a1, title="Morning Tea", theme="Food", content="I drink hot tea every morning.")
        self.client.force_login(self.user)

    def test_rg8_validation_checks_length_and_safety(self):
        ok, _ = validate_generated_text("This is a nice simple sentence for beginners.", self.a1)
        self.assertTrue(ok)
        too_short, _ = validate_generated_text("Hi.", self.b1)
        self.assertFalse(too_short)
        bad_word, _ = validate_generated_text("This sentence contains fuck and should fail validation.", self.a1)
        self.assertFalse(bad_word)

    @patch("learning.llm._call_gemini_structured")
    def test_generate_dictation_text_with_gemini_mock(self, mock_gemini):
        mock_gemini.return_value = {
            "title": "At the Stadium",
            "theme": "Sport",
            "level": "A1",
            "content": "We watch a great football match at the stadium every Saturday afternoon.",
            "keywords": ["stadium", "Saturday", "afternoon"],
        }
        text_obj = generate_dictation_text(self.a1, user=self.user, theme="Sport")
        self.assertIsNotNone(text_obj)
        self.assertEqual(text_obj.origin, Text.Origin.LLM)
        self.assertEqual(text_obj.theme, "Sport")
        self.assertIn("stadium", text_obj.keywords)

    @patch("learning.llm._call_gemini_structured")
    def test_next_text_auto_generates_when_bank_exhausted(self, mock_gemini):
        mock_gemini.return_value = {
            "title": "New AI Text",
            "theme": "Technology",
            "level": "A1",
            "content": "My sister uses her computer every day to learn English online.",
            "keywords": ["computer", "online"],
        }
        # Valide le seul texte existant
        session = DictationSession.objects.create(user=self.user, text=self.t1, max_duration_seconds=300)
        submit_session(session, "I drink hot tea every morning.")
        nxt = next_text(self.user, self.a1)
        self.assertEqual(nxt.title, "New AI Text")

    def test_submission_populates_llm_feedback_vocabulary_streak_and_badges(self):
        current_level(self.user)
        session = DictationSession.objects.create(user=self.user, text=self.t1, max_duration_seconds=300)
        sub = submit_session(session, "I drink hot tee every morning")
        self.assertTrue(sub.llm_feedback)
        self.assertIn("error_explanations", sub.llm_feedback)
        # "tea" a été mal orthographié -> ajouté au carnet de vocabulaire
        self.assertTrue(VocabularyEntry.objects.filter(user=self.user, word="tea").exists())
        # Série quotidienne et badge "Première dictée" créés
        streak = Streak.objects.get(user=self.user)
        self.assertEqual(streak.current_streak, 1)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__code="first_dictation").exists())

    def test_vocabulary_review_doubles_interval(self):
        entry = VocabularyEntry.objects.create(user=self.user, word="schedule", interval_days=2)
        self.client.post(reverse("learning:vocabulary_review", args=[entry.pk]), {"result": "known"})
        entry.refresh_from_db()
        self.assertEqual(entry.interval_days, 4)

    def test_placement_test_recommends_and_allows_step_down_only(self):
        from learning.views import PLACEMENT_SENTENCES

        post_data = {f"sentence_{code}": sent for code, sent in PLACEMENT_SENTENCES}
        resp = self.client.post(reverse("learning:placement"), post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(current_level(self.user), self.b1)

        # L'utilisateur choisit de descendre en A2
        self.client.post(reverse("learning:placement"), {"choose_level": "A2", "max_allowed": "B1"})
        self.assertEqual(current_level(self.user), self.a2)

    def test_exam_validation_unlocks_next_level(self):
        self.a1.requires_exam = True
        self.a1.required_texts = 1
        self.a1.save()
        current_level(self.user)
        # 1er texte validé -> passe en statut EXAM
        s1 = DictationSession.objects.create(user=self.user, text=self.t1, max_duration_seconds=300)
        submit_session(s1, "I drink hot tea every morning.")
        prog = UserLevelProgress.objects.get(user=self.user, level=self.a1)
        self.assertEqual(prog.status, UserLevelProgress.Status.EXAM)

        # Réussite de la dictée d'examen -> débloque A2
        t_exam = Text.objects.create(level=self.a1, title="Exam A1", content="She goes to school by bus every day.")
        s2 = DictationSession.objects.create(user=self.user, text=t_exam, max_duration_seconds=300)
        submit_session(s2, "She goes to school by bus every day.")
        self.assertEqual(current_level(self.user), self.a2)

    def test_history_and_profile_pages_load(self):
        self.assertEqual(self.client.get(reverse("dictation:history")).status_code, 200)
        self.assertEqual(self.client.get(reverse("learning:vocabulary")).status_code, 200)
        self.assertEqual(self.client.get(reverse("learning:badges")).status_code, 200)
        self.assertEqual(self.client.get(reverse("learning:progression")).status_code, 200)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)

    def test_cloze_mode_displays_guided_hint_on_session_page(self):
        resp = self.client.post(
            reverse("dictation:start"),
            {
                "mode": "cloze",
                "speed": "1.00",
                "pause_seconds": 5,
                "repeats_per_segment": 1,
                "duration_minutes": 3,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mode guidé (texte à trous)")
        self.assertContains(resp, "_____")


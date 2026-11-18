from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from learning.models import Level, Text, UserLevelProgress
from learning.services import current_level, level_stats, promote_if_eligible

from .models import DictationSession
from .scoring import score_dictation
from .services import submit_session

REF = "The cat sat on the mat. It was happy."


class ScoringTests(SimpleTestCase):
    def test_perfect(self):
        self.assertEqual(score_dictation(REF, REF).score, 100.0)

    def test_empty_typed_text_scores_zero(self):
        result = score_dictation(REF, "")
        self.assertEqual(result.missing, 9)
        self.assertEqual(result.word_score, 0.0)

    def test_minor_spelling_gets_half_credit(self):
        result = score_dictation("The weather is nice", "The wether is nice", form_weight=0)
        self.assertEqual(result.minor, 1)
        self.assertEqual(result.score, 87.5)

    def test_missing_and_extra_words(self):
        result = score_dictation("I like green apples", "I like very green apples", form_weight=0)
        self.assertEqual(result.extra, 1)
        self.assertEqual(result.score, 93.8)

    def test_punctuation_and_caps_only_cost_form_weight(self):
        result = score_dictation(REF, "the cat sat on the mat it was happy")
        self.assertEqual(result.word_score, 1.0)
        self.assertLess(result.score, 100)
        self.assertGreater(result.score, 85)

    def test_form_weight_zero_ignores_punctuation(self):
        self.assertEqual(score_dictation(REF, "the cat sat on the mat it was happy", form_weight=0).score, 100.0)

    def test_empty_reference_raises(self):
        with self.assertRaises(ValueError):
            score_dictation("", "anything")


class ProgressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("felix", "f@example.com", "pass12345!")
        self.a1 = Level.objects.create(
            code="A1", name="Débutant", order=1, min_words=1, max_words=40,
            text_pass_score=70, required_texts=2, required_average=80, average_window=2,
        )
        self.a2 = Level.objects.create(code="A2", name="Élémentaire", order=2, min_words=1, max_words=70)
        self.t1 = Text.objects.create(level=self.a1, title="T1", content="I like tea")
        self.t2 = Text.objects.create(level=self.a1, title="T2", content="She reads books")

    def _session(self, text):
        return DictationSession.objects.create(user=self.user, text=text, max_duration_seconds=300)

    def test_first_level_assigned_on_first_visit(self):
        self.assertEqual(current_level(self.user), self.a1)

    def test_failing_score_does_not_validate_text(self):
        current_level(self.user)
        submit_session(self._session(self.t1), "totally different")
        self.assertEqual(level_stats(self.user, self.a1)["validated_count"], 0)

    def test_best_score_kept_and_text_validated(self):
        current_level(self.user)
        submit_session(self._session(self.t1), "nothing")
        submit_session(self._session(self.t1), "I like tea")
        stats = level_stats(self.user, self.a1)
        self.assertEqual(stats["validated_count"], 1)
        self.assertEqual(stats["average"], 100.0)

    def test_promotion_after_required_texts_and_average(self):
        current_level(self.user)
        submit_session(self._session(self.t1), "I like tea")
        self.assertIsNone(promote_if_eligible(self.user))  # 1 texte sur 2 seulement
        submit_session(self._session(self.t2), "She reads books")
        self.assertEqual(current_level(self.user), self.a2)

    def test_exam_blocks_direct_promotion(self):
        self.a1.requires_exam = True
        self.a1.save()
        current_level(self.user)
        submit_session(self._session(self.t1), "I like tea")
        submit_session(self._session(self.t2), "She reads books")
        progress = UserLevelProgress.objects.get(user=self.user, level=self.a1)
        self.assertEqual(progress.status, UserLevelProgress.Status.EXAM)
        self.assertEqual(current_level(self.user), self.a1)

    def test_expired_session_is_flagged_and_still_scored(self):
        session = self._session(self.t1)
        session.started_at = timezone.now() - timedelta(seconds=400)
        session.save()
        submission = submit_session(session, "I like tea")
        session.refresh_from_db()
        self.assertEqual(session.status, DictationSession.Status.EXPIRED)
        self.assertEqual(submission.score, 100.0)

    def test_session_cannot_be_submitted_twice(self):
        session = self._session(self.t1)
        first = submit_session(session, "I like tea")
        second = submit_session(session, "something else")
        self.assertEqual(first.pk, second.pk)
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, 15)  # 10 + 5 (sans faute), une seule fois

    def test_speed_default(self):
        self.assertEqual(self._session(self.t1).speed, Decimal("1.00"))


# ---------- Écran de dictée ----------
from django.urls import reverse  # noqa: E402

from .rendering import render_reference  # noqa: E402
from .segments import split_segments  # noqa: E402


class SegmentTests(SimpleTestCase):
    def test_splits_on_sentences(self):
        self.assertEqual(split_segments("I like tea. She reads books! Do you?"),
                         ["I like tea.", "She reads books!", "Do you?"])

    def test_long_sentence_split_on_commas(self):
        text = "After the long game on Saturday afternoon, we went to a small shop and bought some cold ice cream."
        segments = split_segments(text)
        self.assertEqual(len(segments), 2)
        self.assertEqual(" ".join(segments), text)

    def test_short_fragments_are_not_isolated(self):
        segments = split_segments("Last Saturday, my friends and I played football after school and then we all went home.")
        self.assertTrue(all(len(s.split()) >= 3 for s in segments))


class RenderingTests(SimpleTestCase):
    def test_marks_errors_and_escapes_html(self):
        result = score_dictation("I like <b>green</b> apples.", "I lik green apples")
        html = str(render_reference("I like <b>green</b> apples.", result.errors))
        self.assertIn("&lt;", html)
        self.assertNotIn("<b>", html)
        self.assertNotIn("</b>", html)
        self.assertIn('class="w-ok"', html)


class DictationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ama", "a@example.com", "pass12345!")
        self.other = get_user_model().objects.create_user("kofi", "k@example.com", "pass12345!")
        self.a1 = Level.objects.create(code="A1", name="Débutant", order=1, min_words=1, max_words=40,
                                       required_texts=2, required_average=80, average_window=2)
        self.a2 = Level.objects.create(code="A2", name="Élémentaire", order=2, min_words=1, max_words=70)
        self.t1 = Text.objects.create(level=self.a1, title="T1", content="I like tea. She reads books.")
        self.t2 = Text.objects.create(level=self.a1, title="T2", content="We play football today.")
        self.client.force_login(self.user)

    def _start(self, **extra):
        data = {"speed": "1.00", "pause_seconds": 5, "repeats_per_segment": 2, "duration_minutes": 3, **extra}
        return self.client.post(reverse("dictation:start"), data)

    def test_start_creates_session_with_settings(self):
        response = self._start()
        session = DictationSession.objects.get()
        self.assertRedirects(response, reverse("dictation:session", args=[session.pk]))
        self.assertEqual(session.text, self.t1)
        self.assertEqual(session.max_duration_seconds, 180)
        self.assertEqual(session.repeats_per_segment, 2)

    def test_invalid_settings_do_not_create_session(self):
        self._start(pause_seconds=99)
        self.assertEqual(DictationSession.objects.count(), 0)

    def test_pending_session_is_resumed(self):
        self._start()
        response = self.client.get(reverse("dictation:start"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DictationSession.objects.count(), 1)

    def test_session_page_does_not_leak_text_to_html_as_plain_content(self):
        self._start()
        session = DictationSession.objects.get()
        response = self.client.get(reverse("dictation:session", args=[session.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="session-config"')  # segments transmis au lecteur vocal
        self.assertContains(response, "Envoyer pour correction")

    def test_submit_then_result(self):
        self._start()
        session = DictationSession.objects.get()
        response = self.client.post(reverse("dictation:submit", args=[session.pk]),
                                    {"typed_text": "I like tea. She reads books.", "replay_count": "3"})
        self.assertRedirects(response, reverse("dictation:result", args=[session.pk]))
        session.refresh_from_db()
        self.assertEqual(session.replay_count, 3)
        page = self.client.get(reverse("dictation:result", args=[session.pk]))
        self.assertContains(page, "100 %")
        self.assertContains(page, "Texte validé")
        self.assertContains(page, "Texte suivant")

    def test_failed_text_offers_retry_of_same_text(self):
        self._start()
        session = DictationSession.objects.get()
        self.client.post(reverse("dictation:submit", args=[session.pk]), {"typed_text": "nothing"})
        page = self.client.get(reverse("dictation:result", args=[session.pk]))
        self.assertContains(page, "Refaire ce texte")
        # RG1 : le même texte est reproposé tant qu'il n'est pas validé
        self._start()
        self.assertEqual(DictationSession.objects.latest("pk").text, self.t1)

    def test_expired_session_page_has_zero_remaining_and_late_submit_is_accepted(self):
        self._start()
        session = DictationSession.objects.get()
        session.started_at = timezone.now() - timedelta(seconds=1000)
        session.save()
        page = self.client.get(reverse("dictation:session", args=[session.pk]))
        self.assertContains(page, '"remaining": 0')
        self.client.post(reverse("dictation:submit", args=[session.pk]), {"typed_text": "I like tea."})
        session.refresh_from_db()
        self.assertEqual(session.status, DictationSession.Status.EXPIRED)

    def test_cannot_access_someone_elses_session(self):
        self._start()
        session = DictationSession.objects.get()
        self.client.force_login(self.other)
        for name in ("session", "result"):
            self.assertEqual(self.client.get(reverse(f"dictation:{name}", args=[session.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dictation:submit", args=[session.pk])).status_code, 404)

    def test_submit_requires_post_and_login(self):
        self._start()
        session = DictationSession.objects.get()
        self.assertEqual(self.client.get(reverse("dictation:submit", args=[session.pk])).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dictation:start")).status_code, 302)

    def test_level_up_banner_after_last_required_text(self):
        for text, typed in ((self.t1, "I like tea. She reads books."), (self.t2, "We play football today.")):
            self.client.post(reverse("dictation:start"), {"speed": "1.00", "pause_seconds": 5,
                             "repeats_per_segment": 1, "duration_minutes": 3})
            session = DictationSession.objects.latest("pk")
            self.client.post(reverse("dictation:submit", args=[session.pk]), {"typed_text": typed})
        page = self.client.get(reverse("dictation:result", args=[session.pk]))
        self.assertContains(page, "Niveau supérieur débloqué")
        self.assertContains(page, "A2")

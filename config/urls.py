from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as accounts_views
from dictation import views as dictation_views
from learning import views as learning_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", accounts_views.home, name="home"),
    # Authentification & Profil (accessibles sous /accounts/... ET directement à la racine /login/, /signup/, etc.)
    path("login/", auth_views.LoginView.as_view()),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("signup/", accounts_views.signup),
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("logout/", auth_views.LogoutView.as_view()),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", accounts_views.profile),
    path("accounts/profile/", accounts_views.profile, name="profile"),
    path("accounts/password-reset/", accounts_views.CustomPasswordResetView.as_view(), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # Raccourcis racine pratiques vers les écrans principaux
    path("history/", dictation_views.history),
    path("vocabulary/", learning_views.vocabulary_list),
    path("progression/", learning_views.progression_view),
    path("badges/", learning_views.badges_view),
    path("placement/", learning_views.placement_test),
    # Apps complètes
    path("administration/", include("learning.backoffice_urls")),
    path("dictation/", include("dictation.urls")),
    path("learning/", include("learning.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

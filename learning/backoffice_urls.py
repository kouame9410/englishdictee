from django.urls import path

from . import backoffice

app_name = "backoffice"

urlpatterns = [
    path("", backoffice.dashboard, name="dashboard"),
    path("texts/", backoffice.texts_list, name="texts"),
    path("texts/new/", backoffice.text_create, name="text_create"),
    path("texts/<int:pk>/edit/", backoffice.text_edit, name="text_edit"),
    path("texts/<int:pk>/delete/", backoffice.text_delete, name="text_delete"),
    path("texts/generate/", backoffice.text_generate, name="text_generate"),
    path("levels/", backoffice.levels_list, name="levels"),
    path("levels/new/", backoffice.level_create, name="level_create"),
    path("levels/<int:pk>/edit/", backoffice.level_edit, name="level_edit"),
    path("users/", backoffice.users_list, name="users"),
    path("users/<int:pk>/edit/", backoffice.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", backoffice.user_delete, name="user_delete"),
    path("submissions/", backoffice.submissions_list, name="submissions"),
    path("settings/", backoffice.settings_and_badges, name="settings"),
]


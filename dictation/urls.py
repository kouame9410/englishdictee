from django.urls import path

from . import views

app_name = "dictation"

urlpatterns = [
    path("", views.start, name="start"),
    path("history/", views.history, name="history"),
    path("skip/<int:text_pk>/", views.skip_text, name="skip_text"),
    path("session/<int:pk>/", views.session, name="session"),
    path("session/<int:pk>/begin/", views.begin_session, name="begin"),
    path("session/<int:pk>/cancel/", views.cancel_session, name="cancel"),
    path("session/<int:pk>/submit/", views.submit, name="submit"),
    path("session/<int:pk>/result/", views.result, name="result"),
]

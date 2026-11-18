from django.urls import path

from . import views

app_name = "learning"

urlpatterns = [
    path("progression/", views.progression_view, name="progression"),
    path("vocabulary/", views.vocabulary_list, name="vocabulary"),
    path("vocabulary/<int:pk>/review/", views.vocabulary_review, name="vocabulary_review"),
    path("placement/", views.placement_test, name="placement"),
    path("step-down/", views.step_down_level, name="step_down"),
    path("badges/", views.badges_view, name="badges"),
]


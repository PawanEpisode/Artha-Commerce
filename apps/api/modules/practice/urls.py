"""
URL routing for Practice Engine API.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("sessions/", views.SessionListCreateView.as_view(), name="practice-session-list-create"),
    path("sessions/<uuid:session_id>/", views.SessionDetailView.as_view(), name="practice-session-detail"),
    path(
        "sessions/<uuid:session_id>/answers/<uuid:item_id>/",
        views.SaveAnswerView.as_view(),
        name="practice-save-answer",
    ),
    path(
        "sessions/<uuid:session_id>/answers/<uuid:item_id>/check/",
        views.CheckAnswerView.as_view(),
        name="practice-check-answer",
    ),
    path(
        "sessions/<uuid:session_id>/answers/<uuid:item_id>/mistake-reason/",
        views.MistakeReasonView.as_view(),
        name="practice-mistake-reason",
    ),
    path("sessions/active/", views.ActiveSessionView.as_view(), name="practice-active-session"),
    path("sessions/<uuid:session_id>/start/", views.StartSessionView.as_view(), name="practice-start-session"),
    path("sessions/<uuid:session_id>/pause/", views.PauseSessionView.as_view(), name="practice-pause-session"),
    path("sessions/<uuid:session_id>/resume/", views.ResumeSessionView.as_view(), name="practice-resume-session"),
    path("sessions/<uuid:session_id>/submit/", views.SubmitSessionView.as_view(), name="practice-submit-session"),
    path("sessions/<uuid:session_id>/retake/", views.RetakeSessionView.as_view(), name="practice-retake-session"),
    path("progress/chapters/", views.ProgressByChapterView.as_view(), name="practice-progress-chapters"),
    path(
        "progress/chapters/<uuid:chapter_id>/", views.ProgressByChapterView.as_view(), name="practice-progress-chapter"
    ),
    path("bookmarks/", views.BookmarksListView.as_view(), name="practice-bookmarks-list"),
    path("mistakes/", views.MistakesListView.as_view(), name="practice-mistakes-list"),
    path(
        "questions/<uuid:question_id>/state/",
        views.QuestionStateUpdateView.as_view(),
        name="practice-question-state-update",
    ),
]

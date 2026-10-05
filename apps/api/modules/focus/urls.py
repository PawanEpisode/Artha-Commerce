from django.urls import path

from . import views

urlpatterns = [
    path("focus/settings/", views.SettingsView.as_view(), name="focus-settings"),
    path("focus/timer/", views.TimerView.as_view(), name="focus-timer"),
    path("focus/timer/start/", views.TimerStartView.as_view(), name="focus-timer-start"),
    path("focus/timer/pause/", views.TimerPauseView.as_view(), name="focus-timer-pause"),
    path("focus/timer/resume/", views.TimerResumeView.as_view(), name="focus-timer-resume"),
    path("focus/timer/extend/", views.TimerExtendView.as_view(), name="focus-timer-extend"),
    path("focus/timer/complete/", views.TimerCompleteView.as_view(), name="focus-timer-complete"),
    path("focus/timer/skip-break/", views.TimerSkipBreakView.as_view(), name="focus-timer-skip-break"),
    path("focus/timer/heartbeat/", views.TimerHeartbeatView.as_view(), name="focus-timer-heartbeat"),
    path("focus/timer/claim/", views.TimerClaimView.as_view(), name="focus-timer-claim"),
    path("focus/timer/end/", views.TimerEndView.as_view(), name="focus-timer-end"),
    path("focus/timer/context/", views.TimerContextView.as_view(), name="focus-timer-context"),
    path("focus/sessions/", views.SessionListView.as_view(), name="focus-sessions"),
    path("focus/sessions/<uuid:session_id>/", views.SessionDetailView.as_view(), name="focus-session"),
    path("focus/data/", views.DataView.as_view(), name="focus-data"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("tracking/stopwatch/", views.StopwatchView.as_view(), name="tracking-stopwatch"),
    path("tracking/stopwatch/start/", views.StopwatchStartView.as_view(), name="tracking-stopwatch-start"),
    path("tracking/stopwatch/pause/", views.StopwatchPauseView.as_view(), name="tracking-stopwatch-pause"),
    path("tracking/stopwatch/resume/", views.StopwatchResumeView.as_view(), name="tracking-stopwatch-resume"),
    path("tracking/stopwatch/stop/", views.StopwatchStopView.as_view(), name="tracking-stopwatch-stop"),
    path("tracking/stopwatch/context/", views.StopwatchContextView.as_view(), name="tracking-stopwatch-context"),
    path("tracking/stopwatch/idle/", views.StopwatchIdleView.as_view(), name="tracking-stopwatch-idle"),
    path("tracking/sessions/", views.SessionListView.as_view(), name="tracking-sessions"),
    path("tracking/sessions/export.csv", views.SessionExportView.as_view(), name="tracking-sessions-export"),
    path("tracking/sessions/undo/", views.SessionUndoView.as_view(), name="tracking-sessions-undo"),
    path("tracking/sessions/merge/", views.SessionMergeView.as_view(), name="tracking-sessions-merge"),
    path("tracking/sessions/<uuid:session_id>/", views.SessionDetailView.as_view(), name="tracking-session"),
    path("tracking/sessions/<uuid:session_id>/split/", views.SessionSplitView.as_view(), name="tracking-session-split"),
    path("tracking/auto/", views.AutoCaptureView.as_view(), name="tracking-auto"),
    path("tracking/goals/", views.GoalsView.as_view(), name="tracking-goals"),
    path("tracking/settings/", views.SettingsView.as_view(), name="tracking-settings"),
    path("tracking/reports/summary/", views.SummaryView.as_view(), name="tracking-report-summary"),
    path("tracking/reports/series/", views.SeriesView.as_view(), name="tracking-report-series"),
    path("tracking/reports/breakdown/", views.BreakdownView.as_view(), name="tracking-report-breakdown"),
    path("tracking/reports/heatmap/", views.HeatmapView.as_view(), name="tracking-report-heatmap"),
    path("tracking/reports/hours/", views.HoursView.as_view(), name="tracking-report-hours"),
    path("tracking/reports/time-vs-coverage/", views.TimeVsCoverageView.as_view(), name="tracking-report-coverage"),
    path("tracking/reports/weekly-summary/", views.WeeklySummaryView.as_view(), name="tracking-report-weekly"),
    path("tracking/reports/export.csv", views.ReportExportView.as_view(), name="tracking-report-export"),
    path("tracking/data/", views.DataView.as_view(), name="tracking-data"),
]

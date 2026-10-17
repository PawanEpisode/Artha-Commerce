"""
URL routing for Performance Analytics (F-10).
"""

from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view(), name="analytics-overview"),
    path("performance/", views.PerformanceView.as_view(), name="analytics-performance"),
    path("trends/", views.TrendsView.as_view(), name="analytics-trends"),
    path("weak-topics/", views.WeakTopicsView.as_view(), name="analytics-weak-topics"),
    path("fix-sets/", views.FixSetsView.as_view(), name="analytics-fix-sets"),
    path("fix/", views.FixSetsView.as_view(), name="analytics-fix"),
    path("speed/", views.SpeedView.as_view(), name="analytics-speed"),
    path("mistakes/", views.MistakesView.as_view(), name="analytics-mistakes"),
    path("readiness/", views.ReadinessView.as_view(), name="analytics-readiness"),
    path("refresh/", views.RefreshView.as_view(), name="analytics-refresh"),
    path("settings/", views.SettingsView.as_view(), name="analytics-settings"),
    path("goals/", views.GoalsView.as_view(), name="analytics-goals"),
    path("reports/", views.ReportsView.as_view(), name="analytics-reports"),
    path("shares/", views.ShareCreateView.as_view(), name="analytics-shares"),
    path("shares/<str:token>/", views.PublicShareDetailView.as_view(), name="analytics-share-detail"),
]

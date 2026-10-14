from django.urls import path

from . import views

urlpatterns = [
    path("today/open/", views.OpenView.as_view(), name="today-open"),
    path("today/plan/", views.PlanView.as_view(), name="today-plan"),
    path("today/preview/", views.PreviewView.as_view(), name="today-preview"),
    path("today/history/", views.HistoryView.as_view(), name="today-history"),
    path("today/settings/", views.SettingsView.as_view(), name="today-settings"),
]

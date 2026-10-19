"""
URLs for Progression and Level Transition (F-18).
"""

from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.ProgressionStatusView.as_view(), name="progression-status"),
    path("transition/", views.TransitionView.as_view(), name="progression-transition"),
    path("transition/rollback/", views.TransitionRollbackView.as_view(), name="progression-rollback"),
    path("articleship/", views.ArticleshipView.as_view(), name="progression-articleship"),
    path("vault/", views.VaultEnrollmentsView.as_view(), name="progression-vault"),
    path("history/", views.TransitionHistoryView.as_view(), name="progression-history"),
]

"""
URL routes for F-11 Paper Analysis and Recommendations.
"""

from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    # Student endpoints
    path("recommendations/", views.RecommendationsView.as_view(), name="pa-recommendations"),
    path("subjects/", views.SubjectStatusesView.as_view(), name="pa-subject-statuses"),
    path("subjects/<str:subject_key>/stats/", views.ChapterStatsView.as_view(), name="pa-chapter-stats"),
    path("subjects/<str:subject_key>/patterns/", views.PatternsView.as_view(), name="pa-patterns"),
    path("chapters/<str:chapter_key>/history/", views.ChapterHistoryView.as_view(), name="pa-chapter-history"),
    path("asked-summary/", views.AskedSummaryView.as_view(), name="pa-asked-summary"),
    path("settings/", views.StudentSettingsView.as_view(), name="pa-settings"),
    path("flags/", views.FlagCreateView.as_view(), name="pa-flags"),

    # Plan endpoints
    path("plan/preview/", views.PlanPreviewView.as_view(), name="pa-plan-preview"),
    path("plan/active/", views.ActivePlanView.as_view(), name="pa-plan-active"),
    path("plan/adopt/", views.PlanAdoptView.as_view(), name="pa-plan-adopt"),
    path("plan/replan/", views.PlanReplanView.as_view(), name="pa-plan-replan"),
    path("plan/items/<str:item_id>/", views.PlanItemDetailView.as_view(), name="pa-plan-item-detail"),

    # Editorial/Admin endpoints
    path("papers/", views.PaperListCreateView.as_view(), name="pa-paper-list-create"),
    path("papers/<str:paper_id>/", views.PaperDetailView.as_view(), name="pa-paper-detail"),
    path("papers/<str:paper_id>/import/", views.PaperImportView.as_view(), name="pa-paper-import"),
    path("papers/<str:paper_id>/suggest/", views.PaperSuggestView.as_view(), name="pa-paper-suggest"),
    path("papers/<str:paper_id>/publish/", views.PaperPublishView.as_view(), name="pa-paper-publish"),
    path("papers/<str:paper_id>/unpublish/", views.PaperUnpublishView.as_view(), name="pa-paper-unpublish"),
    path("questions/<str:question_id>/allocations/", views.QuestionAllocationsView.as_view(), name="pa-question-allocations"),
    path("questions/<str:question_id>/confirm/", views.QuestionConfirmView.as_view(), name="pa-question-confirm"),
    path("questions/<str:question_id>/qa/", views.QuestionQaView.as_view(), name="pa-question-qa"),
    path("backtests/", views.BacktestCreateView.as_view(), name="pa-backtests"),

    # Public SEO endpoint
    path("public/<str:course>/<str:level>/<str:subject_key>/", views.PublicAnalysisView.as_view(), name="pa-public-analysis"),
]

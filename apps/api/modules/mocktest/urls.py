"""
URL patterns for F-08 Mock Tests and MTP.
"""

from __future__ import annotations

from django.urls import path
from . import views

app_name = "mocktest"

urlpatterns = [
    # Public (SEO / Anonymous)
    path("public/series/", views.PublicSeriesListView.as_view(), name="public-series-list"),
    path("public/series/<slug:slug>/", views.PublicSeriesDetailView.as_view(), name="public-series-detail"),
    path("public/papers/<str:public_id>/", views.PublicPaperDetailView.as_view(), name="public-paper-detail"),

    # Papers & Blueprint
    path("papers/", views.PaperListView.as_view(), name="paper-list"),
    path("papers/new/", views.PaperCreateView.as_view(), name="paper-create"),
    path("papers/overlay/", views.PaperOverlayView.as_view(), name="paper-overlay"),
    path("papers/key-string/parse/", views.PaperKeyStringParseView.as_view(), name="paper-keystring-parse"),
    path("papers/<str:paper_id_or_public_id>/", views.PaperDetailView.as_view(), name="paper-detail"),
    path("papers/<str:id>/blueprint/", views.PaperBlueprintView.as_view(), name="paper-blueprint"),

    # Builder
    path("builder/preview/", views.BuilderPreviewView.as_view(), name="builder-preview"),
    path("builder/generate/", views.BuilderGenerateView.as_view(), name="builder-generate"),

    # Attempts
    path("attempts/", views.AttemptListCreateView.as_view(), name="attempt-list-create"),
    path("attempts/compare/", views.AttemptCompareView.as_view(), name="attempt-compare"),
    path("attempts/<uuid:id>/", views.AttemptStateView.as_view(), name="attempt-state"),
    path("attempts/<uuid:id>/bundle/", views.AttemptBundleView.as_view(), name="attempt-bundle"),
    path("attempts/<uuid:id>/clock/", views.AttemptClockView.as_view(), name="attempt-clock"),
    path("attempts/<uuid:id>/accept/", views.AttemptAcceptInstructionsView.as_view(), name="attempt-accept"),
    path("attempts/<uuid:id>/writing/start/", views.AttemptStartWritingView.as_view(), name="attempt-writing-start"),
    path("attempts/<uuid:id>/lease/", views.AttemptLeaseView.as_view(), name="attempt-lease"),
    path("attempts/<uuid:id>/heartbeat/", views.AttemptHeartbeatView.as_view(), name="attempt-heartbeat"),
    path("attempts/<uuid:id>/answers/", views.AttemptAnswersBulkView.as_view(), name="attempt-answers-bulk"),
    path("attempts/<uuid:id>/answers/<int:position>/", views.AttemptAnswerSingleView.as_view(), name="attempt-answer-single"),
    path("attempts/<uuid:id>/sections/<str:key>/close/", views.AttemptCloseSectionView.as_view(), name="attempt-close-section"),
    path("attempts/<uuid:id>/pause/", views.AttemptPauseView.as_view(), name="attempt-pause"),
    path("attempts/<uuid:id>/resume/", views.AttemptResumeView.as_view(), name="attempt-resume"),
    path("attempts/<uuid:id>/submit/", views.AttemptSubmitView.as_view(), name="attempt-submit"),
    path("attempts/<uuid:id>/result/", views.AttemptResultView.as_view(), name="attempt-result"),
    path("attempts/<uuid:id>/review/", views.AttemptReviewView.as_view(), name="attempt-review"),
    path("attempts/<uuid:id>/events/", views.AttemptEventsView.as_view(), name="attempt-events"),
    path("attempts/<uuid:id>/retake/", views.AttemptRetakeView.as_view(), name="attempt-retake"),
    path("attempts/<uuid:id>/pages/", views.AttemptPagesView.as_view(), name="attempt-pages"),
    path("attempts/<uuid:id>/percentile/", views.AttemptPercentileView.as_view(), name="attempt-percentile"),

    # Settings & Reference Data
    path("settings/", views.SettingsView.as_view(), name="settings"),
    path("series/", views.SeriesListView.as_view(), name="series-list"),
    path("series/<slug:slug>/", views.SeriesDetailView.as_view(), name="series-detail"),
    path("formats/", views.ExamFormatListView.as_view(), name="formats-list"),

    # Admin (Editor)
    path("admin/papers/<uuid:id>/publish/", views.AdminPaperPublishView.as_view(), name="admin-paper-publish"),
    path("admin/papers/<uuid:id>/revise/", views.AdminPaperReviseView.as_view(), name="admin-paper-revise"),
    path("admin/papers/<uuid:id>/key-release/", views.AdminPaperKeyReleaseView.as_view(), name="admin-paper-key-release"),
]

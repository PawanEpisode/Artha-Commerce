"""
URL routing for MCQ Bank module.
Mounted under /api/v1/mcq/.
"""

from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    # Student endpoints
    path("home/", views.McqHomeView.as_view(), name="mcq-home"),
    path("subjects/<str:subject_key>/tiles/", views.SubjectTilesView.as_view(), name="mcq-subject-tiles"),
    path(
        "subjects/<str:subject_key>/chapters/<str:chapter_key>/",
        views.ChapterDetailView.as_view(),
        name="mcq-chapter-detail",
    ),
    path("quick-start/", views.QuickStartView.as_view(), name="mcq-quick-start"),
    path("sets/", views.SetsListView.as_view(), name="mcq-sets-list"),
    path("sets/<slug:slug>/", views.SetDetailView.as_view(), name="mcq-set-detail"),
    path("sets/<slug:slug>/start/", views.SetPracticeStartView.as_view(), name="mcq-set-start"),
    path("sets/<slug:slug>/click/", views.SetClickView.as_view(), name="mcq-set-click"),
    path("external-logs/", views.ExternalLogListView.as_view(), name="mcq-external-logs"),
    path("external-logs/<uuid:log_id>/", views.ExternalLogDetailView.as_view(), name="mcq-external-log-detail"),
    path("presets/", views.PresetsListView.as_view(), name="mcq-presets-list"),
    path("presets/<uuid:preset_id>/use/", views.PresetUseView.as_view(), name="mcq-preset-use"),
    path("presets/<uuid:preset_id>/", views.PresetDetailView.as_view(), name="mcq-preset-detail"),
    path("patterns/resolve/", views.PatternResolveView.as_view(), name="mcq-pattern-resolve"),
    path("blueprint/preview/", views.BlueprintPreviewView.as_view(), name="mcq-blueprint-preview"),
    path("references/", views.ReferenceSourcesView.as_view(), name="mcq-references"),
    # Adaptive endpoints (R3)
    path("adaptive/start/", views.AdaptiveStartView.as_view(), name="mcq-adaptive-start"),
    path("adaptive/<uuid:run_id>/next/", views.AdaptiveNextRoundView.as_view(), name="mcq-adaptive-next"),
    path("adaptive/<uuid:run_id>/stop/", views.AdaptiveStopView.as_view(), name="mcq-adaptive-stop"),
    # Staff / Editor endpoints
    path("editor/sets/<uuid:set_id>/publish/", views.SetPublishView.as_view(), name="mcq-editor-set-publish"),
    path("editor/sets/<uuid:set_id>/withdraw/", views.SetWithdrawView.as_view(), name="mcq-editor-set-withdraw"),
    path(
        "editor/patterns/<uuid:pattern_id>/verify/",
        views.PatternVerifyView.as_view(),
        name="mcq-editor-pattern-verify",
    ),
]

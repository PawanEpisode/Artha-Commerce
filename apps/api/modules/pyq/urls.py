"""
URL routes for PYQ module.
"""

from __future__ import annotations

from django.urls import path

from .views import (
    ChapterPracticeStartView,
    ChapterPyqsView,
    EditorImportPaperView,
    EditorPublishPaperView,
    EditorWithdrawPaperView,
    PaperDetailView,
    PaperLinkOpenView,
    PaperPracticeStartView,
    PapersListView,
)

app_name = "pyq"

urlpatterns = [
    # Student / Public
    path("papers/", PapersListView.as_view(), name="paper-list"),
    path("papers/<str:pk>/", PaperDetailView.as_view(), name="paper-detail"),
    path("papers/<str:pk>/links/<str:link_id>/open/", PaperLinkOpenView.as_view(), name="paper-link-open"),
    path("papers/<str:pk>/practice/", PaperPracticeStartView.as_view(), name="paper-practice-start"),
    path("chapters/<str:chapter_id>/", ChapterPyqsView.as_view(), name="chapter-pyqs"),
    path("chapters/<str:chapter_id>/practice/", ChapterPracticeStartView.as_view(), name="chapter-practice-start"),
    # Editor
    path("editor/import-paper/", EditorImportPaperView.as_view(), name="editor-import-paper"),
    path("editor/papers/<str:pk>/publish/", EditorPublishPaperView.as_view(), name="editor-publish-paper"),
    path("editor/papers/<str:pk>/withdraw/", EditorWithdrawPaperView.as_view(), name="editor-withdraw-paper"),
]

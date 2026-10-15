"""
Question bank URL patterns (F-06 ERD 9).
"""

from django.urls import path

from . import views

urlpatterns = [
    # Public endpoints (read-only, cached)
    path(
        "questionbank/public/questions/",
        views.PublicQuestionsView.as_view(),
        name="qb_public_questions",
    ),
    path(
        "questionbank/public/questions/<uuid:pk>/",
        views.PublicQuestionDetailView.as_view(),
        name="qb_public_question_detail",
    ),
    path(
        "questionbank/public/facets/",
        views.PublicFacetsView.as_view(),
        name="qb_public_facets",
    ),
    # Authenticated question endpoints
    path(
        "questionbank/questions/",
        views.CreateDraftView.as_view(),
        name="qb_create_draft",
    ),
    path(
        "questionbank/questions/<uuid:pk>/playable/",
        views.QuestionPlayableView.as_view(),
        name="qb_question_playable",
    ),
    path(
        "questionbank/questions/<uuid:pk>/live/",
        views.SaveLiveView.as_view(),
        name="qb_save_live",
    ),
    path(
        "questionbank/questions/<uuid:pk>/review/",
        views.QuestionReviewView.as_view(),
        name="qb_question_review",
    ),
    path(
        "questionbank/questions/<uuid:pk>/report/",
        views.ReportErrorView.as_view(),
        name="qb_report_error",
    ),
    # Editor endpoints
    path(
        "questionbank/editor/reviews/<uuid:pk>/decide/",
        views.DecideReviewView.as_view(),
        name="qb_decide_review",
    ),
    path(
        "questionbank/editor/versions/<uuid:pk>/publish/",
        views.PublishVersionView.as_view(),
        name="qb_publish_version",
    ),
    path(
        "questionbank/editor/verify/",
        views.VerifyView.as_view(),
        name="qb_verify",
    ),
    path(
        "questionbank/editor/merge/",
        views.MergeDuplicateView.as_view(),
        name="qb_merge_duplicate",
    ),
    path(
        "questionbank/editor/import-csv/",
        views.ImportQuestionsCsvView.as_view(),
        name="qb_import_csv",
    ),
    path(
        "questionbank/editor/review-queue/",
        views.EditorReviewQueueView.as_view(),
        name="qb_review_queue",
    ),
    path(
        "questionbank/editor/reports/",
        views.EditorReportsListView.as_view(),
        name="qb_editor_reports",
    ),
    path(
        "questionbank/editor/reports/<uuid:pk>/resolve/",
        views.EditorResolveReportView.as_view(),
        name="qb_resolve_report",
    ),
]

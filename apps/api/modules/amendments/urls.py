from __future__ import annotations

from django.urls import path

from . import views

app_name = "amendments"

urlpatterns = [
    # Student workspace routes (Authenticated, flag-guarded)
    path("me/summary/", views.MySummaryView.as_view(), name="me-summary"),
    path("me/cards/", views.MyChangesView.as_view(), name="me-cards"),
    path("me/cards/<str:public_id>/", views.MyChangeDetailView.as_view(), name="me-card-detail"),
    path("me/archive/", views.MyArchiveView.as_view(), name="me-archive"),
    path("me/data/", views.UserDataDeleteView.as_view(), name="me-data-delete"),
    path("me/export/", views.UserDataExportView.as_view(), name="me-export"),
    # Student card actions
    path("cards/<str:public_id>/reviewed/", views.CardReviewedView.as_view(), name="card-reviewed"),
    path("cards/<str:public_id>/saved/", views.CardSavedView.as_view(), name="card-saved"),
    path("cards/bulk-reviewed/", views.BulkReviewedView.as_view(), name="cards-bulk-reviewed"),
    path("cards/<str:public_id>/report/", views.CardReportView.as_view(), name="card-report"),
    # Chapter panel embed
    path("chapters/<uuid:chapter_id>/", views.ChapterAmendmentsView.as_view(), name="chapter-amendments"),
    # Public indexable routes (Unauthenticated, strict allow-list)
    path("public/hub/", views.PublicHubView.as_view(), name="public-hub"),
    path("public/documents/<slug:slug>/", views.PublicDocumentView.as_view(), name="public-document"),
    path("public/cards/<str:public_id>/", views.PublicCardView.as_view(), name="public-card"),
    path("public/sitemap/", views.PublicSitemapView.as_view(), name="public-sitemap"),
    path("public/<str:course_code>/<str:level_code>/", views.PublicLevelView.as_view(), name="public-level"),
    path(
        "public/<str:course_code>/<str:level_code>/<str:term_code>/", views.PublicTermView.as_view(), name="public-term"
    ),
    path(
        "public/<str:course_code>/<str:level_code>/<str:term_code>/<str:subject_key>/",
        views.PublicPaperView.as_view(),
        name="public-paper",
    ),
]

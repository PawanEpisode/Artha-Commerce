"""
URL configuration for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "material"

urlpatterns = [
    # Public SEO facts
    path(
        "public/subjects/<str:course>/<str:level>/<str:subject>/material/",
        views.PublicSubjectMaterialView.as_view(),
        name="public_subject_material",
    ),
    # Works & Chapters
    path("works/", views.WorkListView.as_view(), name="work_list"),
    path("works/<str:work_key>/", views.WorkDetailView.as_view(), name="work_detail"),
    path(
        "works/<str:work_key>/chapters/<str:chapter_key>/items/",
        views.ChapterItemsView.as_view(),
        name="chapter_items",
    ),
    path(
        "works/<str:work_key>/changes/",
        views.EditionChangesView.as_view(),
        name="edition_changes",
    ),
    path(
        "chapters/<str:chapter_id>/summary/",
        views.ChapterSummaryView.as_view(),
        name="chapter_summary",
    ),
    # Items
    path("items/<str:item_id>/", views.ItemDetailView.as_view(), name="item_detail"),
    path("items/<str:item_id>/report/", views.ItemReportView.as_view(), name="item_report"),
    # Student Progress
    path("progress/batch/", views.ProgressBatchView.as_view(), name="progress_batch"),
    path("progress/<str:item_id>/", views.ProgressUpdateView.as_view(), name="progress_update"),
    path("me/editions/<str:work_key>/", views.UserEditionView.as_view(), name="user_edition"),
    path(
        "me/editions/<str:work_key>/dismiss-banner/",
        views.UserBannerDismissView.as_view(),
        name="user_banner_dismiss",
    ),
    # Registry & Providers
    path("providers/", views.ProviderListView.as_view(), name="provider_list"),
    path("me/providers/", views.UserProviderListView.as_view(), name="user_provider_list"),
    path("me/providers/<str:pk>/", views.UserProviderDetailView.as_view(), name="user_provider_detail"),
    # Private Checklists
    path("mine/works/", views.PrivateWorkListView.as_view(), name="private_works"),
    # DPDP
    path("me/export/", views.UserDataExportView.as_view(), name="user_data_export"),
    path("me/data/", views.UserDataDeleteView.as_view(), name="user_data_delete"),
    # Admin
    path("admin/providers/<str:pk>/merge/", views.AdminProviderMergeView.as_view(), name="admin_provider_merge"),
    path("admin/works/", views.AdminWorkCreateView.as_view(), name="admin_work_create"),
    path("admin/works/<str:work_id>/editions/", views.AdminEditionCreateView.as_view(), name="admin_edition_create"),
    path("admin/editions/<str:pk>/import/", views.AdminEditionImportView.as_view(), name="admin_edition_import"),
    path("admin/editions/<str:pk>/match/", views.AdminEditionMatchView.as_view(), name="admin_edition_match"),
    path("admin/matches/<str:pk>/", views.AdminMatchDecisionView.as_view(), name="admin_match_decide"),
    path("admin/editions/<str:pk>/publish/", views.AdminEditionPublishView.as_view(), name="admin_edition_publish"),
    path("admin/editions/<str:pk>/withdraw/", views.AdminEditionWithdrawView.as_view(), name="admin_edition_withdraw"),
    path("admin/editions/<str:pk>/restore/", views.AdminEditionRestoreView.as_view(), name="admin_edition_restore"),
]

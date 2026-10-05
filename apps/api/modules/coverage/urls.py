from django.urls import path

from . import views

urlpatterns = [
    path("coverage/enrollments/", views.EnrollmentListView.as_view(), name="coverage-enrollments"),
    path(
        "coverage/enrollments/<uuid:enrollment_id>/", views.EnrollmentDetailView.as_view(), name="coverage-enrollment"
    ),
    path(
        "coverage/enrollments/<uuid:enrollment_id>/electives/",
        views.EnrollmentElectivesView.as_view(),
        name="coverage-enrollment-electives",
    ),
    path("coverage/overview/", views.OverviewView.as_view(), name="coverage-overview"),
    path("coverage/subjects/<uuid:subject_id>/", views.SubjectCoverageView.as_view(), name="coverage-subject"),
    path(
        "coverage/subjects/<uuid:subject_id>/exclusion/",
        views.SubjectExclusionView.as_view(),
        name="coverage-subject-exclusion",
    ),
    path("coverage/chapters/<uuid:chapter_id>/", views.ChapterCoverageView.as_view(), name="coverage-chapter"),
    path("coverage/chapters/<uuid:chapter_id>/read/", views.ChapterReadView.as_view(), name="coverage-chapter-read"),
    path("coverage/chapters/<uuid:chapter_id>/confidence/", views.ConfidenceView.as_view(), name="coverage-confidence"),
    path(
        "coverage/chapters/<uuid:chapter_id>/exclusion/",
        views.ChapterExclusionView.as_view(),
        name="coverage-exclusion",
    ),
    path("coverage/topics/<uuid:topic_id>/", views.TopicTickView.as_view(), name="coverage-topic"),
    path("coverage/catchup/", views.CatchupView.as_view(), name="coverage-catchup"),
    path("coverage/events/", views.EventView.as_view(), name="coverage-events"),
    path("coverage/due/", views.DueView.as_view(), name="coverage-due"),
    path("coverage/settings/", views.SettingsView.as_view(), name="coverage-settings"),
    path("coverage/settings/targets/preview/", views.TargetsPreviewView.as_view(), name="coverage-targets-preview"),
    path("coverage/", views.DataView.as_view(), name="coverage-data"),
    path("coverage/export/", views.DataView.as_view(), name="coverage-export"),
]

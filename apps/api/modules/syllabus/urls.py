from django.urls import path

from . import views

urlpatterns = [
    path("syllabus/courses/", views.CourseListView.as_view(), name="syllabus-courses"),
    path("syllabus/courses/<slug:course>/levels/<slug:level>/", views.LevelDetailView.as_view(), name="syllabus-level"),
    path(
        "syllabus/courses/<slug:course>/levels/<slug:level>/subjects/<slug:subject>/",
        views.SubjectByKeyView.as_view(),
        name="syllabus-subject-by-key",
    ),
    path(
        "syllabus/courses/<slug:course>/levels/<slug:level>/subjects/<slug:subject>/chapters/<slug:chapter>/",
        views.ChapterByKeyView.as_view(),
        name="syllabus-chapter-by-key",
    ),
    path("syllabus/subjects/<uuid:subject_id>/", views.SubjectDetailView.as_view(), name="syllabus-subject"),
    path("syllabus/chapters/<uuid:chapter_id>/", views.ChapterDetailView.as_view(), name="syllabus-chapter"),
    path("syllabus/terms/", views.TermListView.as_view(), name="syllabus-terms"),
    path("syllabus/sitemap/", views.SitemapPathsView.as_view(), name="syllabus-sitemap"),
    path("syllabus/reports/", views.ReportView.as_view(), name="syllabus-report"),
    path(
        "admin/syllabus/schemes/<uuid:scheme_id>/publish/",
        views.SchemeStateView.as_view(action="publish"),
        name="syllabus-scheme-publish",
    ),
    path(
        "admin/syllabus/schemes/<uuid:scheme_id>/retire/",
        views.SchemeStateView.as_view(action="retire"),
        name="syllabus-scheme-retire",
    ),
]

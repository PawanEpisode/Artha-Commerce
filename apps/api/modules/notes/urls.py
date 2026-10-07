from django.urls import path

from . import views

urlpatterns = [
    # Account data and cron: never gated by the `notes` flag.
    path("notes/", views.DeleteAllView.as_view(), name="notes-delete-all"),
    path("notes/export/", views.ExportView.as_view(), name="notes-export"),
    path("notes/internal/tick/", views.TickView.as_view(), name="notes-tick"),
    # Notes
    path("notes/notes/", views.NoteListCreateView.as_view(), name="notes-list"),
    path("notes/notes/changes/", views.ChangesView.as_view(), name="notes-changes"),
    path("notes/notes/<uuid:note_id>/", views.NoteDetailView.as_view(), name="notes-detail"),
    path("notes/notes/<uuid:note_id>/restore/", views.NoteRestoreView.as_view(), name="notes-restore"),
    path("notes/notes/<uuid:note_id>/versions/", views.VersionListView.as_view(), name="notes-versions"),
    path("notes/notes/<uuid:note_id>/versions/<int:rev>/", views.VersionDetailView.as_view(), name="notes-version"),
    path(
        "notes/notes/<uuid:note_id>/versions/<int:rev>/restore/",
        views.VersionRestoreView.as_view(),
        name="notes-version-restore",
    ),
    path("notes/clips/", views.ClipView.as_view(), name="notes-clips"),
    # Aggregation and search
    path("notes/aggregate/", views.AggregateView.as_view(), name="notes-aggregate"),
    path("notes/aggregate/counts/", views.AggregateCountsView.as_view(), name="notes-aggregate-counts"),
    path("notes/chapters/<slug:chapter_key>/overview/", views.ChapterOverviewView.as_view(), name="notes-overview"),
    path("notes/search/", views.SearchView.as_view(), name="notes-search"),
    # Tags, suggestions, settings
    path("notes/tags/", views.TagListCreateView.as_view(), name="notes-tags"),
    path("notes/tags/<uuid:tag_id>/", views.TagDetailView.as_view(), name="notes-tag"),
    path("notes/items/tags/", views.ItemTagsView.as_view(), name="notes-item-tags"),
    path("notes/items/chapter-suggest/", views.ChapterSuggestView.as_view(), name="notes-chapter-suggest"),
    path("notes/settings/", views.SettingsView.as_view(), name="notes-settings"),
    path("notes/usage/", views.UsageView.as_view(), name="notes-usage"),
]

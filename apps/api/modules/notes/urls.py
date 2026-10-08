from django.urls import path

from . import views
from . import views_ai as ai
from . import views_annotations as marks
from . import views_documents as docs
from . import views_ocr_export as ocrx
from . import views_replace as replace

urlpatterns = [
    # `DELETE notes/` (on the list view) and these two stay open with the `notes` flag off.
    path("notes/", views.NoteListCreateView.as_view(), name="notes-list"),
    path("notes/export/", views.ExportView.as_view(), name="notes-export"),
    path("notes/internal/tick/", views.TickView.as_view(), name="notes-tick"),
    path("notes/changes/", views.ChangesView.as_view(), name="notes-changes"),
    path("notes/<uuid:note_id>/", views.NoteDetailView.as_view(), name="notes-detail"),
    path("notes/<uuid:note_id>/restore/", views.NoteRestoreView.as_view(), name="notes-restore"),
    path("notes/<uuid:note_id>/versions/", views.VersionListView.as_view(), name="notes-versions"),
    path("notes/<uuid:note_id>/versions/<int:rev>/", views.VersionDetailView.as_view(), name="notes-version"),
    path(
        "notes/<uuid:note_id>/versions/<int:rev>/restore/",
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
    # Documents (R2, flag `notes_pdf`)
    path("notes/documents/", docs.DocumentListCreateView.as_view(), name="notes-documents"),
    path("notes/documents/<uuid:document_id>/", docs.DocumentDetailView.as_view(), name="notes-document"),
    path(
        "notes/documents/<uuid:document_id>/complete/",
        docs.DocumentCompleteView.as_view(),
        name="notes-document-complete",
    ),
    path("notes/documents/<uuid:document_id>/abort/", docs.DocumentAbortView.as_view(), name="notes-document-abort"),
    path(
        "notes/documents/<uuid:document_id>/restore/", docs.DocumentRestoreView.as_view(), name="notes-document-restore"
    ),
    path(
        "notes/documents/<uuid:document_id>/chapters/",
        docs.DocumentRangesView.as_view(),
        name="notes-document-chapters",
    ),
    path(
        "notes/documents/<uuid:document_id>/progress/",
        docs.DocumentProgressView.as_view(),
        name="notes-document-progress",
    ),
    path(
        "notes/documents/<uuid:document_id>/processing/",
        docs.DocumentProcessingView.as_view(),
        name="notes-document-processing",
    ),
    path(
        "notes/documents/<uuid:document_id>/pages/text/",
        docs.DocumentPageTextView.as_view(),
        name="notes-document-text",
    ),
    path("notes/documents/<uuid:document_id>/search/", docs.DocumentSearchView.as_view(), name="notes-document-search"),
    # OCR and export (R2): `notes_pdf`, the archive only `notes`
    path(
        "notes/documents/<uuid:document_id>/replace/",
        replace.DocumentReplaceView.as_view(),
        name="notes-document-replace",
    ),
    path(
        "notes/documents/<uuid:document_id>/attention/",
        replace.AttentionView.as_view(),
        name="notes-document-attention",
    ),
    path(
        "notes/documents/<uuid:document_id>/attention/<uuid:item_id>/",
        replace.AttentionItemView.as_view(),
        name="notes-document-attention-item",
    ),
    path(
        "notes/documents/<uuid:document_id>/resumable/",
        replace.ResumableView.as_view(),
        name="notes-document-resumable",
    ),
    path(
        "notes/documents/<uuid:document_id>/resumable/parts/",
        replace.ResumablePartsView.as_view(),
        name="notes-document-resumable-parts",
    ),
    path(
        "notes/documents/<uuid:document_id>/resumable/complete/",
        replace.ResumableFinishView.as_view(),
        name="notes-document-resumable-complete",
    ),
    path(
        "notes/documents/<uuid:document_id>/unlock/", replace.DocumentUnlockView.as_view(), name="notes-document-unlock"
    ),
    path("notes/documents/<uuid:document_id>/ocr/", ocrx.DocumentOcrView.as_view(), name="notes-document-ocr"),
    path(
        "notes/documents/<uuid:document_id>/exports/", ocrx.DocumentExportView.as_view(), name="notes-document-exports"
    ),
    path("notes/export/archive/", ocrx.ArchiveView.as_view(), name="notes-export-archive"),
    path("notes/exports/<uuid:export_id>/", ocrx.ExportDetailView.as_view(), name="notes-export-detail"),
    # Marks (R2): the delta feed, single writes, one batch endpoint and the recall card
    path(
        "notes/documents/<uuid:document_id>/annotations/",
        marks.DocumentAnnotationsView.as_view(),
        name="notes-document-annotations",
    ),
    path("notes/annotations/batch/", marks.AnnotationBatchView.as_view(), name="notes-annotations-batch"),
    path("notes/annotations/<uuid:annotation_id>/", marks.AnnotationDetailView.as_view(), name="notes-annotation"),
    path(
        "notes/annotations/<uuid:annotation_id>/restore/",
        marks.AnnotationRestoreView.as_view(),
        name="notes-annotation-restore",
    ),
    path(
        "notes/annotations/<uuid:annotation_id>/card/", marks.AnnotationCardView.as_view(), name="notes-annotation-card"
    ),
    # AI (R3, flag `notes_ai`, fail closed); taking things back needs no flag
    path("notes/ai/consent/", ai.ConsentView.as_view(), name="notes-ai-consent"),
    path("notes/ai/consent/withdraw/", ai.ConsentWithdrawView.as_view(), name="notes-ai-consent-withdraw"),
    path("notes/ai/summary/", ai.SummaryListCreateView.as_view(), name="notes-ai-summary"),
    path("notes/ai/summary/<uuid:job_id>/", ai.SummaryDetailView.as_view(), name="notes-ai-summary-detail"),
    path("notes/ai/summary/<uuid:job_id>/accept/", ai.SummaryAcceptView.as_view(), name="notes-ai-summary-accept"),
    path("notes/ai/summary/<uuid:job_id>/discard/", ai.SummaryDiscardView.as_view(), name="notes-ai-summary-discard"),
    path("notes/ai/summary/<uuid:job_id>/cancel/", ai.SummaryCancelView.as_view(), name="notes-ai-summary-cancel"),
    path("notes/ai/ocr/<uuid:job_id>/", ai.AiOcrDetailView.as_view(), name="notes-ai-ocr-detail"),
    path("notes/ai/ocr/<uuid:job_id>/cancel/", ai.AiOcrCancelView.as_view(), name="notes-ai-ocr-cancel"),
]

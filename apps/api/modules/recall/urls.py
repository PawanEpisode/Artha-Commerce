from django.urls import path

from . import views

urlpatterns = [
    path("recall/cards/", views.CardListCreateView.as_view(), name="recall-cards"),
    path("recall/cards/from-selection/", views.CardFromSelectionView.as_view(), name="recall-cards-selection"),
    path("recall/cards/undo-delete/", views.CardUndoView.as_view(), name="recall-cards-undo"),
    path("recall/cards/bulk/", views.CardBulkView.as_view(), name="recall-cards-bulk"),
    path("recall/cards/<uuid:card_id>/", views.CardDetailView.as_view(), name="recall-card"),
    path("recall/cards/<uuid:card_id>/reviews/", views.CardHistoryView.as_view(), name="recall-card-history"),
    *(
        path(
            f"recall/cards/<uuid:card_id>/{slug}/",
            views.CardActionView.as_view(action=action),
            name=f"recall-card-{slug}",
        )
        for slug, action in (
            ("suspend", "suspend"),
            ("unsuspend", "unsuspend"),
            ("bury", "bury"),
            ("reset", "reset"),
            ("recheck-ok", "recheck_ok"),
        )
    ),
]
urlpatterns += [
    path("recall/reviews/", views.ReviewSubmitView.as_view(), name="recall-reviews"),
    path("recall/reviews/batch/", views.ReviewBatchView.as_view(), name="recall-reviews-batch"),
    path("recall/reviews/undo/", views.ReviewUndoView.as_view(), name="recall-reviews-undo"),
    path("recall/sessions/", views.SessionOpenView.as_view(), name="recall-sessions"),
    path("recall/sessions/<uuid:session_id>/close/", views.SessionCloseView.as_view(), name="recall-session-close"),
    path("recall/catchup/rebalance/", views.RebalanceView.as_view(), name="recall-rebalance"),
    path("recall/vacation/", views.VacationView.as_view(), name="recall-vacation"),
    path("recall/today/", views.TodayView.as_view(), name="recall-today"),
    path("recall/queue/", views.QueueView.as_view(), name="recall-queue"),
    path("recall/pack/", views.PackView.as_view(), name="recall-pack"),
    path("recall/forgotten/", views.ForgottenView.as_view(), name="recall-forgotten"),
    *(
        path(f"recall/stats/{name}/", views.StatsView.as_view(report=name), name=f"recall-stats-{name}")
        for name in ("summary", "retention", "forecast", "chapters")
    ),
    path("recall/settings/", views.SettingsView.as_view(), name="recall-settings"),
    path("recall/internal/tick/", views.TickView.as_view(), name="recall-tick"),
]
urlpatterns += [
    path("recall/decks/library/", views.DeckLibraryView.as_view(), name="recall-deck-library"),
    path("recall/decks/subscribed/", views.DeckSubscribedView.as_view(), name="recall-deck-subscribed"),
    path("recall/decks/<uuid:deck_id>/", views.DeckDetailView.as_view(), name="recall-deck"),
    path("recall/decks/<uuid:deck_id>/subscribe/", views.DeckSubscribeView.as_view(), name="recall-deck-subscribe"),
    path(
        "recall/subscriptions/<uuid:subscription_id>/unsubscribe/",
        views.SubscriptionActionView.as_view(action="unsubscribe"),
        name="recall-unsubscribe",
    ),
    path(
        "recall/subscriptions/<uuid:subscription_id>/resubscribe/",
        views.SubscriptionActionView.as_view(action="resubscribe"),
        name="recall-resubscribe",
    ),
    path("recall/items/<uuid:item_id>/report/", views.ItemReportView.as_view(), name="recall-item-report"),
    path("recall/export/", views.ExportView.as_view(), name="recall-export"),
    path("recall/export/cards.csv", views.CsvExportView.as_view(which="cards"), name="recall-export-cards"),
    path("recall/export/reviews.csv", views.CsvExportView.as_view(which="reviews"), name="recall-export-reviews"),
    path("recall/erase/", views.EraseView.as_view(), name="recall-erase"),
]

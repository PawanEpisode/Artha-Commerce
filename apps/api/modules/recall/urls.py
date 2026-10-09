from django.urls import path

from . import views

urlpatterns = [
    path("recall/cards/", views.CardListCreateView.as_view(), name="recall-cards"),
    path("recall/cards/from-selection/", views.CardFromSelectionView.as_view(), name="recall-cards-selection"),
    path("recall/cards/undo-delete/", views.CardUndoView.as_view(), name="recall-cards-undo"),
    path("recall/cards/bulk/", views.CardBulkView.as_view(), name="recall-cards-bulk"),
    path("recall/cards/<uuid:card_id>/", views.CardDetailView.as_view(), name="recall-card"),
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

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

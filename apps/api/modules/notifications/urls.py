from django.urls import path

from . import views

urlpatterns = [
    path("notifications/settings/", views.SettingsView.as_view(), name="notifications-settings"),
    path("notifications/categories/", views.CategoriesView.as_view(), name="notifications-categories"),
    path("notifications/preferences/", views.PreferencesView.as_view(), name="notifications-preferences"),
    path("notifications/permission-state/", views.PermissionStateView.as_view(), name="notifications-permission-state"),
    path("notifications/devices/", views.DevicesView.as_view(), name="notifications-devices"),
    path("notifications/devices/<uuid:device_id>/", views.DeviceDetailView.as_view(), name="notifications-device"),
    path(
        "notifications/devices/<uuid:device_id>/test/", views.DeviceTestView.as_view(), name="notifications-device-test"
    ),
    path("notifications/inbox/", views.InboxView.as_view(), name="notifications-inbox"),
    path("notifications/inbox/read/", views.InboxReadView.as_view(), name="notifications-inbox-read"),
    path(
        "notifications/inbox/<uuid:notification_id>/click/",
        views.InboxClickView.as_view(),
        name="notifications-inbox-click",
    ),
    path("notifications/digest/", views.DigestView.as_view(), name="notifications-digest"),
    path("notifications/thought/today/", views.ThoughtTodayView.as_view(), name="notifications-thought-today"),
    # Public: the one-time token of a notification button is the credential (views/actions.py).
    path("notifications/actions/", views.ActionsView.as_view(), name="notifications-actions"),
    # Public: the signed link in the weekly email is the credential (views/unsubscribe.py).
    path("notifications/unsubscribe/", views.UnsubscribeView.as_view(), name="notifications-unsubscribe"),
    # Machines only: signature or cron secret, no student auth (views/internal.py).
    path(
        "notifications/internal/jobs/<uuid:job_id>/fire/",
        views.JobFireView.as_view(),
        name="notifications-internal-fire",
    ),
    path("notifications/internal/sweep/", views.SweepView.as_view(), name="notifications-internal-sweep"),
]

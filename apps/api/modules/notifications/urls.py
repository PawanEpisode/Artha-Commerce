from django.urls import path

from . import views

urlpatterns = [
    path("notifications/settings/", views.SettingsView.as_view(), name="notifications-settings"),
    path("notifications/categories/", views.CategoriesView.as_view(), name="notifications-categories"),
    path("notifications/preferences/", views.PreferencesView.as_view(), name="notifications-preferences"),
    path("notifications/permission-state/", views.PermissionStateView.as_view(), name="notifications-permission-state"),
]

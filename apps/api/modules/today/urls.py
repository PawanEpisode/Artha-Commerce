from django.urls import path

from . import views

urlpatterns = [
    path("today/open/", views.OpenView.as_view(), name="today-open"),
    path("today/plan/", views.PlanView.as_view(), name="today-plan"),
    path("today/preview/", views.PreviewView.as_view(), name="today-preview"),
    path("today/history/", views.HistoryView.as_view(), name="today-history"),
    path("today/settings/", views.SettingsView.as_view(), name="today-settings"),
    path("today/plan/regenerate/", views.RegenerateView.as_view(), name="today-regenerate"),
    path("today/tasks/", views.TasksView.as_view(), name="today-tasks"),
    path("today/tasks/<uuid:task_id>/", views.TaskDetailView.as_view(), name="today-task"),
    path("today/tasks/<uuid:task_id>/start/", views.StartView.as_view(), name="today-task-start"),
    path("today/tasks/<uuid:task_id>/complete/", views.CompleteView.as_view(), name="today-task-complete"),
    path("today/tasks/<uuid:task_id>/skip/", views.SkipView.as_view(), name="today-task-skip"),
    path("today/tasks/<uuid:task_id>/snooze/", views.SnoozeView.as_view(), name="today-task-snooze"),
    path("today/tasks/<uuid:task_id>/swap/", views.SwapView.as_view(), name="today-task-swap"),
    path("today/tasks/<uuid:task_id>/undo/", views.UndoView.as_view(), name="today-task-undo"),
]

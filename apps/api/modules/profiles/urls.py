from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),
    path("me/avatar/", views.AvatarView.as_view(), name="me-avatar"),
    path("me/avatar/preset/", views.AvatarPresetView.as_view(), name="me-avatar-preset"),
    path("me/export/", views.ExportView.as_view(), name="me-export"),
    path("me/onboarding/", views.OnboardingView.as_view(), name="me-onboarding"),
    path("me/onboarding/complete/", views.OnboardingCompleteView.as_view(), name="me-onboarding-complete"),
    path("me/onboarding/steps/<slug:key>/", views.OnboardingStepView.as_view(), name="me-onboarding-step"),
    path("me/onboarding/steps/<slug:key>/skip/", views.OnboardingSkipView.as_view(), name="me-onboarding-skip"),
]

from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    name = "modules.profiles"
    label = "profiles"

    def ready(self):
        from .onboarding_steps import register_built_in_handlers

        register_built_in_handlers()

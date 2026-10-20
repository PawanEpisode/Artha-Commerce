from django.apps import AppConfig


class AmendmentsConfig(AppConfig):
    name = "modules.amendments"
    label = "amendments"
    verbose_name = "Statutory Amendments"

    def ready(self):
        pass

from django.apps import AppConfig


class MediaConfig(AppConfig):
    name = "modules.media"
    label = "media"

    def ready(self):
        from core import jobs, registry

        from . import services

        jobs.register_handler(services.JOB_DELETE, services.run_delete_job)
        jobs.register_handler(services.JOB_EXPIRE, services.run_expire_job)
        jobs.register_handler(services.JOB_SCAN, services.run_scan_job)
        registry.register_eraser("media", services.delete_all_for_user)
        registry.register_exporter("media", services.export_for_user)

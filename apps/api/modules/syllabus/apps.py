from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_staff_groups(sender=None, using="default", **kwargs):
    """
    Two groups for content staff, kept in sync after every migrate (safe to repeat):
    - Syllabus editors: edit the taxonomy and handle reports. Cannot publish.
    - Syllabus publishers: everything editors can do, plus publish and retire schemes.
    Staff users (is_staff) get one of these in the admin; superusers need neither.
    """
    from django.contrib.auth.models import Group, Permission

    editor_models = [
        "course",
        "level",
        "examterm",
        "scheme",
        "syllabusgroup",
        "subject",
        "chapter",
        "topic",
        "chaptermap",
    ]
    codenames = [f"{action}_{model}" for model in editor_models for action in ("view", "add", "change", "delete")]
    codenames += ["view_syllabusreport", "change_syllabusreport"]
    editor_perms = Permission.objects.filter(content_type__app_label="syllabus", codename__in=codenames)

    editors, _ = Group.objects.using(using).get_or_create(name="Syllabus editors")
    editors.permissions.set(editor_perms)
    publishers, _ = Group.objects.using(using).get_or_create(name="Syllabus publishers")
    publish = Permission.objects.filter(content_type__app_label="syllabus", codename="publish_scheme")
    publishers.permissions.set([*editor_perms, *publish])


class SyllabusConfig(AppConfig):
    name = "modules.syllabus"
    label = "syllabus"

    def ready(self):
        post_migrate.connect(ensure_staff_groups, sender=self, dispatch_uid="syllabus.ensure_staff_groups")

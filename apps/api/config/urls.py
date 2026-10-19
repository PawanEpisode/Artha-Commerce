from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ArthaCommerce content admin"
admin.site.site_title = "ArthaCommerce admin"
admin.site.index_title = "Syllabus and support"

urlpatterns = [
    path(settings.ADMIN_PATH, admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("modules.profiles.urls")),
    path("api/v1/", include("modules.syllabus.urls")),
    path("api/v1/", include("modules.coverage.urls")),
    path("api/v1/", include("modules.tracking.urls")),
    path("api/v1/", include("modules.focus.urls")),
    path("api/v1/", include("modules.notifications.urls")),
    path("api/v1/", include("modules.media.urls")),
    path("api/v1/", include("modules.notes.urls")),
    path("api/v1/", include("modules.recall.urls")),
    path("api/v1/", include("modules.today.urls")),
    path("api/v1/", include("modules.questionbank.urls")),
    path("api/v1/practice/", include("modules.practice.urls")),
    path("api/v1/pyq/", include("modules.pyq.urls")),
    path("api/v1/mcq/", include("modules.mcqbank.urls")),
    path("api/v1/analytics/", include("modules.analytics.urls")),
    path("api/v1/paperanalysis/", include("modules.paperanalysis.urls")),
    path("api/v1/progression/", include("modules.progression.urls")),
]

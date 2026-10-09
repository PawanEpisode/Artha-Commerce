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
]

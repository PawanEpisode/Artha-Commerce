from django.urls import path

from . import views

urlpatterns = [
    path("media/uploads/", views.UploadCreateView.as_view(), name="media-upload-create"),
    path(
        "media/uploads/<uuid:attachment_id>/complete/", views.UploadCompleteView.as_view(), name="media-upload-complete"
    ),
    path("media/attachments/<uuid:attachment_id>/url/", views.AttachmentUrlView.as_view(), name="media-attachment-url"),
]

"""
Thin views of the R3 AI features (contract R3). They need the `notes` flag AND `notes_ai`, which FAILS CLOSED (only an explicit on
counts: AI costs money and sends text to Google). Taking things back never needs the flag: withdrawing consent, cancelling a
queued request and discarding a draft only need a signed-in student, like the data export.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from core.permissions import ParsedAPIView, flag_required

from . import serializers as base
from . import serializers_ai as out
from .errors import NotesFeatureDisabled
from .selectors import ai as ai_selectors
from .selectors import get_note
from .services import ai_consent, ai_jobs, summary
from .views import NOTES_FLAG, NotesView

AI_FLAG = "notes_ai"


class AiView(NotesView):
    permission_classes = [
        IsAuthenticated,
        flag_required(NOTES_FLAG, NotesFeatureDisabled),
        flag_required(AI_FLAG, NotesFeatureDisabled, strict=True),
    ]


class AiWriteView(AiView):
    throttle_scope = "notes_ai"


class TakeBackView(ParsedAPIView):
    """Withdraw, cancel, discard: signed in is enough."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notes_write"


def _job_or_404(user_id, job_id, kind: str = "exam_summary"):
    job = ai_selectors.get_job(user_id, job_id)
    if job is None or job.kind != kind:
        raise NotFound("Not found.")
    return job


class ConsentView(AiView):
    def get(self, request):
        return Response(out.consent_out(ai_consent.status(request.user.id)))

    def put(self, request):
        version = self.parse(out.ConsentBody, request.data).validated_data["version"]
        ai_consent.grant(request.user.id, version)
        return Response(out.consent_out(ai_consent.status(request.user.id)))


class ConsentWithdrawView(TakeBackView):
    def delete(self, request):
        report = ai_consent.withdraw(request.user.id)
        return Response({**report, "consent": out.consent_out(ai_consent.status(request.user.id))})


class SummaryListCreateView(AiWriteView):
    def get(self, request):
        chapter_id = self.parse(out.ChapterQuery, request.query_params).validated_data["chapter_id"]
        job = ai_selectors.latest_for_chapter(request.user.id, chapter_id)
        return Response({"job": out.job_out(job) if job else None})

    def post(self, request):
        d = self.parse(out.SummaryBody, request.data).validated_data
        result = summary.request_summary(
            request.user.id,
            client_id=d["client_id"],
            chapter_id=d["chapter_id"],
            include=d.get("include") or summary.INCLUDE,
        )
        code = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
        return Response(out.request_out(result), status=code)


class SummaryDetailView(AiView):
    throttle_scope = "notes_read"

    def get(self, request, job_id):
        return Response(out.job_out(_job_or_404(request.user.id, job_id)))


class SummaryAcceptView(AiWriteView):
    def post(self, request, job_id):
        d = self.parse(out.AcceptBody, request.data).validated_data
        job, note = summary.accept_summary(request.user.id, job_id, body_md=d.get("body_md"), title=d.get("title"))
        card = get_note(request.user.id, note.id)
        return Response({"job": out.job_out(job), "note": base.note_detail(card)})


class SummaryDiscardView(TakeBackView):
    def post(self, request, job_id):
        _job_or_404(request.user.id, job_id)
        return Response(out.job_out(ai_jobs.discard(request.user.id, job_id)))


class SummaryCancelView(TakeBackView):
    def post(self, request, job_id):
        _job_or_404(request.user.id, job_id)
        return Response(out.job_out(ai_jobs.cancel(request.user.id, job_id)))


class AiOcrDetailView(AiView):
    """Progress of an AI page read (the web polls it): `{status, pages, done, failed, ...}`, never any page text."""

    throttle_scope = "notes_read"

    def get(self, request, job_id):
        return Response(out.ocr_job_out(_job_or_404(request.user.id, job_id, "ocr_page_ai")))


class AiOcrCancelView(TakeBackView):
    """Stops a read that has not started (the pages are given back). One that is running finishes the page it is on."""

    def post(self, request, job_id):
        _job_or_404(request.user.id, job_id, "ocr_page_ai")
        return Response(out.ocr_job_out(ai_jobs.cancel(request.user.id, job_id)))

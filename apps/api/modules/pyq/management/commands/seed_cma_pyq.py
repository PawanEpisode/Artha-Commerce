"""
Management command: python manage.py seed_cma_pyq

Retired. It used to create five paper shells (Intermediate 5 to 8 and Final 13, June 2024) with links to icmai.in addresses
that were guessed, never checked, and no questions. The real papers come from the institute's PDFs through
`load_question_bank_seed`, and the PDFs themselves are hosted by us (`publish_pyq_pdfs`) and open in the PDF reader.

What this command does now: removes the shells an earlier run left behind (a paper under the old `pyq:cma:<level>:<subject>`
ref that has no questions), together with their fabricated links. A paper with questions is never touched. Safe to run again.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from modules.pyq.models import PyqPaper


class Command(BaseCommand):
    help = "Remove the empty paper shells (and their made-up links) left by the retired early seeder."

    def handle(self, *args, **options):
        shells = [
            paper
            for paper in PyqPaper.objects.filter(external_ref__startswith="pyq:cma:")
            if not paper.questions.exists()
        ]
        for paper in shells:
            paper.delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {len(shells)} empty legacy paper shell(s)."))

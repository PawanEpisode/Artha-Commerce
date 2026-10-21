"""
Django management command:
    python manage.py upload_source_materials [--bucket BUCKET] [--dry-run]

Uploads Mock Tests, MQP, PTP, and Study Material Paper-Books from Docs/source-material/
to Supabase public Storage buckets, and generates the CDN URL manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from core.storage import StorageError, get_storage, public_url


class Command(BaseCommand):
    help = "Uploads source materials to public Supabase buckets and generates CDN URL manifest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Generate CDN URLs and manifest without transferring network bytes.",
        )
        parser.add_argument(
            "--base-dir",
            default="Docs/source-material",
            help="Path to source materials root.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        base_dir = Path(options["base_dir"])
        if not base_dir.exists():
            base_dir = Path(str(options["base_dir"]).lower())

        if not base_dir.exists():
            self.stdout.write(self.style.ERROR(f"Directory not found: {base_dir}"))
            return

        mock_bucket = getattr(settings, "SUPABASE_MOCKTEST_BUCKET", "mock-tests")
        mat_bucket = getattr(settings, "SUPABASE_STUDY_MATERIAL_BUCKET", "study-material")

        store = None
        if not dry_run:
            try:
                store = get_storage()
                store.ensure_bucket(mock_bucket, public=True)
                store.ensure_bucket(mat_bucket, public=True)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Storage connection notice ({exc}). Operating in manifest mode."))

        manifest: dict[str, str] = {}
        all_pdfs = sorted(base_dir.rglob("*.pdf"))

        self.stdout.write(f"Found {len(all_pdfs)} PDF source files to process.")

        uploaded_count = 0
        for pdf_path in all_pdfs:
            rel_str = str(pdf_path.relative_to(base_dir))
            is_mock = "mock-tests" in str(pdf_path)
            bucket = mock_bucket if is_mock else mat_bucket

            # Normalize destination path
            dest_key = rel_str.replace(" ", "_")

            # Determine public CDN URL
            if store:
                cdn_url = store.public_url(bucket, dest_key)
            else:
                base_url = getattr(settings, "SUPABASE_URL", "https://bqkglnfdhkidajeqlebl.supabase.co").rstrip("/")
                cdn_url = f"{base_url}/storage/v1/object/public/{bucket}/{dest_key.lstrip('/')}"

            manifest[rel_str] = cdn_url

            if store and not dry_run:
                try:
                    data = pdf_path.read_bytes()
                    store.upload(
                        bucket=bucket,
                        path=dest_key,
                        data=data,
                        content_type="application/pdf",
                        cache_control="public, max-age=31536000",
                        upsert=True,
                    )
                    uploaded_count += 1
                except StorageError as se:
                    self.stdout.write(self.style.WARNING(f"  [Storage Skip] {pdf_path.name}: {se}"))
                except Exception as ex:
                    self.stdout.write(self.style.WARNING(f"  [Error] {pdf_path.name}: {ex}"))

        # Save manifest
        manifest_path = base_dir / "cdn_urls_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Indexed {len(manifest)} files. "
                f"Uploaded: {uploaded_count}. Manifest saved at {manifest_path}."
            )
        )

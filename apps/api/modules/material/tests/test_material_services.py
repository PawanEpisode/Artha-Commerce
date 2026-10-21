"""
Integration tests for F-12 material services and endpoints.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
import pytest
from django.utils import timezone

from modules.material import models, selectors, services


USER_ID = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.fixture
def base_syllabus():
    course_id = uuid.uuid4()
    level_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    return {
        "course_id": course_id,
        "level_id": level_id,
        "subject_id": subject_id,
        "subject_key": "taxation",
        "chapter_id": chapter_id,
        "chapter_key": "gst-intro",
    }


@pytest.mark.django_db
def test_full_material_lifecycle(base_syllabus):
    editor_id = uuid.uuid4()
    data = base_syllabus

    # 1. Create provider
    provider = services.create_provider(
        editor_id,
        payload={"name": "ICAI", "kind": models.Provider.Kind.INSTITUTE, "slug": "icai"},
    )
    assert provider.slug == "icai"
    assert provider.status == models.Provider.Status.ACTIVE

    # 2. Create work
    work = services.create_work(
        editor_id,
        payload={
            "provider_id": provider.id,
            "work_key": "ca-inter-taxation-mat",
            "title": "Taxation Study Material",
            "course_id": data["course_id"],
            "level_id": data["level_id"],
            "subject_key": data["subject_key"],
            "subject_id": data["subject_id"],
        },
    )
    assert work.work_key == "ca-inter-taxation-mat"

    # 3. Create draft edition
    edition = services.create_draft_edition(
        editor_id,
        work.id,
        payload={
            "label": "July 2024 Edition",
            "applies_from_term": "2026-05",
            "source_url": "https://icai.org/tax.pdf",
            "page_offset": 6,
        },
    )
    assert edition.status == models.Edition.Status.DRAFT

    # 4. Import index
    items_data = [
        {
            "unit_key": "u1",
            "unit_title": "GST Introduction",
            "printed_label": "Illustration 1",
            "kind": "illustration",
            "page_start": 10,
            "descriptor": "Tax calculation under forward charge",
            "chapter_id": data["chapter_id"],
            "chapter_key": data["chapter_key"],
        },
        {
            "unit_key": "u1",
            "unit_title": "GST Introduction",
            "printed_label": "Illustration 2",
            "kind": "illustration",
            "page_start": 15,
            "descriptor": "Reverse charge mechanism problem",
            "chapter_id": data["chapter_id"],
            "chapter_key": data["chapter_key"],
        },
    ]
    job = services.import_index(editor_id, edition.id, items_data)
    assert job.status == models.ImportJob.Status.IMPORTED
    edition.refresh_from_db()
    assert edition.status == models.Edition.Status.MATCHING
    assert edition.items.count() == 2

    # 5. Run matching
    match_counts = services.run_matching(editor_id, edition.id)
    assert match_counts["new"] == 2
    edition.refresh_from_db()
    assert edition.status == models.Edition.Status.READY

    # 6. Publish edition
    pub_ed = services.publish_edition(editor_id, edition.id)
    assert pub_ed.status == models.Edition.Status.CURRENT
    assert pub_ed.level_at_publish == 1
    work.refresh_from_db()
    assert work.item_count_cached == 2

    # 7. Student progress: mark item done
    first_item = edition.items.first().item
    prog = services.set_progress(
        user_id=USER_ID,
        item_id=first_item.id,
        edition_id=pub_ed.id,
        state=models.Progress.State.DONE,
        note="Remember Section 9(3)",
    )
    assert prog.state == models.Progress.State.DONE
    assert prog.note == "Remember Section 9(3)"

    # 8. Check chapter summary selector
    ch_sum = selectors.chapter_summary(USER_ID, data["chapter_id"])
    assert ch_sum["summary"]["total"] == 2
    assert ch_sum["summary"]["done"] == 1
    assert ch_sum["summary"]["percent"] == 50

    # 9. Set followed provider
    followed = services.set_followed_providers(USER_ID, [provider.id], ["Custom Classes"])
    assert len(followed) == 2

    # 10. DPDP export and delete
    export_data = services.export_for_user(USER_ID)
    assert len(export_data["progress"]) == 1
    assert len(export_data["followed_providers"]) == 2

    del_rep = services.delete_all_for_user(USER_ID)
    assert del_rep["progress"] == 1
    assert del_rep["user_providers"] == 2
    assert models.Progress.objects.filter(user_id=USER_ID).count() == 0

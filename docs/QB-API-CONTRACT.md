# Question Bank API Contract (F-06)

This document is the machine-checked API contract for the Question Bank system (`modules.questionbank`).
Drift is asserted by `apps/api/modules/questionbank/tests/test_contract.py`.

## 1. Endpoints and Throttles

<!-- contract:endpoints -->
| Method | Path | Purpose | Throttle Scope |
| --- | --- | --- | --- |
| GET | `questionbank/public/questions/` | List published questions | `qb_read` |
| GET | `questionbank/public/questions/<uuid:pk>/` | Public question detail card | `qb_read` |
| GET | `questionbank/public/facets/` | Facet counts for filters | `qb_read` |
| POST | `questionbank/questions/` | Create a new question draft | `qb_write` |
| GET | `questionbank/questions/<uuid:pk>/playable/` | Playable question payload (no answers) | `qb_read` |
| PUT | `questionbank/questions/<uuid:pk>/live/` | Save private or link question live | `qb_write` |
| GET | `questionbank/questions/<uuid:pk>/review/` | Review question payload (with answers) | `qb_read` |
| POST | `questionbank/questions/<uuid:pk>/review/` | Submit question for editorial review | `qb_write` |
| POST | `questionbank/questions/<uuid:pk>/report/` | Report an error in a question | `qb_report` |
| POST | `questionbank/editor/reviews/<uuid:pk>/decide/` | Decide on a review item | `qb_write` |
| POST | `questionbank/editor/versions/<uuid:pk>/publish/` | Publish a question version live | `qb_write` |
| POST | `questionbank/editor/verify/` | Verify a question version | `qb_write` |
| POST | `questionbank/editor/merge/` | Merge duplicate questions | `qb_write` |
| POST | `questionbank/editor/import-csv/` | Import multiple questions from CSV | `qb_write` |
| GET | `questionbank/editor/review-queue/` | Editorial review queue | `qb_read` |
| GET | `questionbank/editor/reports/` | List reported questions | `qb_read` |
| POST | `questionbank/editor/reports/<uuid:pk>/resolve/` | Resolve or action question report | `qb_write` |
<!-- /contract:endpoints -->

Throttle scopes: `qb_read` 300 per minute, `qb_write` 60 per minute, `qb_report` 20 per hour, `qb_upload` 100 per hour, `qb_export` 6 per hour, `qb_import` 5 per day, `legal_notice` 5 per hour.

## 2. Playable Payload Keys (No Answers)

<!-- contract:playable-keys -->
question_id,version_id,version_no,kind,position,group,stem_md,marks,negative_applies,suggested_seconds,options,numeric,labels,media,needs_attention
<!-- /contract:playable-keys -->

Playable option keys:
<!-- contract:playable-option-keys -->
id,body_md,pinned
<!-- /contract:playable-option-keys -->

## 3. Review Payload Keys (Includes Answers)

<!-- contract:review-keys -->
question_id,version_id,version_no,kind,position,stem_md,marks,negative_marks,suggested_seconds,options,correct_option_ids,numeric_key,explanation_md,explanation_source,reference_labels,rubric,labels,media,newer_version_available
<!-- /contract:review-keys -->

## 4. Question Card Keys (Search & Lists)

<!-- contract:card-keys -->
id,public_id,kind,stem_head,marks,difficulty,nature,source_name,source_year,source_term_code,is_verified,primary_chapter_id,chapter_key,subject_key,tag_slugs,published_at
<!-- /contract:card-keys -->

## 5. Error Codes

<!-- contract:error-codes -->
feature_disabled,validation_failed,checks_failed,invalid_operation,not_found
<!-- /contract:error-codes -->

## 6. Practice Engine Endpoints and Throttles

<!-- contract:practice-endpoints -->
| Method | Path | Purpose | Throttle Scope |
| --- | --- | --- | --- |
| GET | `sessions/` | List student practice sessions | `qb_read` |
| POST | `sessions/` | Create new practice session | `qb_write` |
| GET | `sessions/<uuid:session_id>/` | Session detail (playable or review) | `qb_read` |
| POST | `sessions/<uuid:session_id>/answers/<uuid:item_id>/` | Save student answer | `qb_write` |
| POST | `sessions/<uuid:session_id>/answers/<uuid:item_id>/check/` | Instant answer check | `qb_write` |
| POST | `sessions/<uuid:session_id>/answers/<uuid:item_id>/mistake-reason/` | Tag mistake reason | `qb_write` |
| POST | `sessions/<uuid:session_id>/pause/` | Pause timed session | `qb_write` |
| POST | `sessions/<uuid:session_id>/resume/` | Resume paused session | `qb_write` |
| POST | `sessions/<uuid:session_id>/submit/` | Submit and finalize session | `qb_write` |
| POST | `sessions/<uuid:session_id>/retake/` | Retake session items | `qb_write` |
| GET | `progress/chapters/` | Progress by chapter batch (E-F06-1) | `qb_read` |
| GET | `progress/chapters/<uuid:chapter_id>/` | Progress for one chapter (E-F06-1) | `qb_read` |
| GET | `bookmarks/` | List student bookmarked questions | `qb_read` |
| GET | `mistakes/` | List recent question mistakes | `qb_read` |
| POST | `questions/<uuid:question_id>/state/` | Update question state flags | `qb_write` |
<!-- /contract:practice-endpoints -->

## 7. Practice Payload Keys

### Session View Keys
<!-- contract:practice-session-view-keys -->
id,mode,title,status,feedback_policy,scoring_profile,question_count,total_marks,time_limit_seconds,deadline_at,score,max_score,score_status,items
<!-- /contract:practice-session-view-keys -->

### Session Item View Keys
<!-- contract:practice-session-item-view-keys -->
position,question_id,kind,stem_md,options,marks_max,negative_max,status,selected_option_ids,numeric_value,numeric_unit,time_spent_ms,marked_for_review,doubt,confidence,result,marks_awarded,negative_applied,explanation_md,feedback
<!-- /contract:practice-session-item-view-keys -->

### Chapter Progress Keys (E-F06-1)
<!-- contract:practice-chapter-progress-keys -->
attempted,correct_last,wrong_last,bookmarked,due,avg_time_ms,last_attempt_at
<!-- /contract:practice-chapter-progress-keys -->

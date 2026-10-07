import type { Note, NoteLink } from './types'

/** Test factories. Not imported by app code. */
export const UNFILED_LINK: NoteLink = {
  level_id: null,
  subject_id: null,
  subject_key: null,
  subject_name: null,
  chapter_id: null,
  chapter_key: null,
  chapter_name: null,
  topic_id: null,
  topic_key: null,
  topic_name: null,
  moved_or_removed: false,
}

export const FILED_LINK: NoteLink = {
  level_id: '11111111-1111-4111-8111-111111111111',
  subject_id: 's1',
  subject_key: 'taxation',
  subject_name: 'Taxation',
  chapter_id: 'c1',
  chapter_key: 'gst-itc',
  chapter_name: 'GST: Input tax credit',
  topic_id: null,
  topic_key: null,
  topic_name: null,
  moved_or_removed: false,
}

export function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    kind: 'note',
    origin: 'typed',
    title: 'Blocked credits',
    snippet: 'ITC is blocked for motor vehicles.',
    body_chars: 40,
    pinned: false,
    is_current_summary: false,
    link: UNFILED_LINK,
    tags: [],
    rev: 1,
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    deleted_at: null,
    purge_after: null,
    client_id: null,
    body_md: 'ITC is blocked for motor vehicles.',
    lang: 'en',
    clip_source: null,
    image_ids: [],
    ...overrides,
  }
}

import { describe, expect, it } from 'vitest'

import type { QueuedWrite } from '~/lib/offline-queue'

import {
  buildLocalNote,
  createBodyOf,
  createKey,
  entryNoteId,
  foldCreateBody,
  hasContent,
  isCreateEntry,
  rekeyEntry,
  tagsKey,
} from './local-note'

const A = '3f2b8c1e-5a4d-4e9b-8c7a-1d2e3f4a5b6c'
const B = '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d'

describe('buildLocalNote', () => {
  it('is an empty, unfiled note that only exists here and already has the revision a create produces', () => {
    const note = buildLocalNote(A, {}, '2026-10-08T10:00:00Z')
    expect(note).toMatchObject({ id: A, client_id: A, title: '', body_md: '', rev: 1, local_only: true, tags: [] })
    expect(note.link.chapter_id).toBeNull()
    expect(note.created_at).toBe('2026-10-08T10:00:00Z')
  })

  it('starts filed under the chapter it was opened from', () => {
    const note = buildLocalNote(A, {
      selection: {
        levelId: 'l',
        subjectId: 's',
        subjectKey: 'tax',
        subjectName: 'Taxation',
        chapterId: 'c1',
        chapterKey: 'itc',
        chapterName: 'ITC',
        topicId: 't1',
        topicKey: 'blocked',
        topicName: 'Blocked',
      },
    })
    expect(createBodyOf(note)).toMatchObject({ chapter_id: 'c1', topic_id: 't1' })
    expect(note.link.chapter_name).toBe('ITC')
  })
})

describe('hasContent', () => {
  it('counts text, a title or a tag, but not whitespace', () => {
    const empty = { title: ' ', body_md: '\n', tags: [] }
    expect(hasContent(empty)).toBe(false)
    expect(hasContent({ ...empty, body_md: 'x' })).toBe(true)
    expect(hasContent({ ...empty, title: 'x' })).toBe(true)
    expect(hasContent({ ...empty, tags: [{ id: 't', name: 'n', color_key: null }] })).toBe(true)
  })
})

describe('foldCreateBody', () => {
  it('lets newer fields win, never erases with undefined and keeps the client id', () => {
    expect(
      foldCreateBody(
        { client_id: A, title: 'a', body_md: 'old', chapter_id: 'c' },
        { client_id: B, body_md: 'new', title: undefined, chapter_id: null },
      ),
    ).toEqual({ client_id: A, title: 'a', body_md: 'new', chapter_id: null })
  })
})

describe('queue entries of a note', () => {
  const entry = (over: Partial<QueuedWrite>): QueuedWrite => ({
    clientId: createKey(A),
    userId: 'u',
    scope: 'notes',
    method: 'PUT',
    path: `/notes/${A}/`,
    body: { client_id: A },
    queuedAt: 1,
    ...over,
  })

  it('finds the note of a create, an edit and a tag write', () => {
    expect(entryNoteId(entry({}))).toBe(A)
    expect(entryNoteId(entry({ method: 'PATCH', clientId: `patch:${A}` }))).toBe(A)
    expect(entryNoteId(entry({ clientId: tagsKey(A), path: '/notes/items/tags/', body: { item_id: A } }))).toBe(A)
    expect(entryNoteId(entry({ path: '/notes/clips/', body: {} }))).toBeNull()
  })

  it('recognises a create by its method and key only', () => {
    expect(isCreateEntry(entry({}))).toBe(true)
    expect(isCreateEntry(entry({ method: 'PATCH', clientId: `patch:${A}` }))).toBe(false)
  })

  it('moves key, path and ids in the body to a new note id', () => {
    expect(rekeyEntry(entry({}), A, B)).toMatchObject({
      clientId: `create:${B}`,
      path: `/notes/${B}/`,
      body: { client_id: B },
    })
    const tags = entry({ clientId: tagsKey(A), path: '/notes/items/tags/', body: { item_id: A, tag_ids: ['t'] } })
    expect(rekeyEntry(tags, A, B)).toMatchObject({ clientId: `tags:${B}`, body: { item_id: B, tag_ids: ['t'] } })
  })
})

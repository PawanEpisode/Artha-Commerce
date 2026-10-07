import { describe, expect, it } from 'vitest'

import { checkBeforeUpload, FALLBACK_UPLOAD_LIMITS, fullQuota, limitsFromUsage, MIB, refusalText } from './upload-check'

const limits = { maxFileMb: 50, maxPages: 1000, maxStorageMb: 500, maxDocuments: 100 }
const pdf = (over: Partial<{ name: string; type: string; bytes: number; pages: number | null }> = {}) => ({
  name: 'tax.pdf',
  type: 'application/pdf',
  bytes: 10 * MIB,
  pages: 100,
  ...over,
})
const room = { storageBytes: 0, documents: 0 }

describe('checkBeforeUpload (nothing moves for a refused file)', () => {
  it('lets a normal PDF through', () => expect(checkBeforeUpload(pdf(), limits, room)).toBeNull())
  it('accepts a PDF whose browser type is empty when the name ends in .pdf', () =>
    expect(checkBeforeUpload(pdf({ type: '', name: 'A.PDF' }), limits, room)).toBeNull())
  it('refuses another type', () => {
    expect(checkBeforeUpload(pdf({ type: 'image/png', name: 'a.png' }), limits, room)).toEqual({ reason: 'type' })
    expect(checkBeforeUpload(pdf({ type: '', name: 'notes.docx' }), limits, room)).toEqual({ reason: 'type' })
  })
  it('refuses a file over the size limit and says by how much it is', () => {
    const refusal = checkBeforeUpload(pdf({ bytes: 63 * MIB }), limits, room)
    expect(refusal).toEqual({ reason: 'too_large', limitMb: 50, bytes: 63 * MIB })
    expect(refusal && refusalText(refusal).title).toBe('50 MB limit (this file 63 MB)')
  })
  it('allows exactly the limit', () => expect(checkBeforeUpload(pdf({ bytes: 50 * MIB }), limits, room)).toBeNull())
  it('refuses too many pages, but not an unknown page count', () => {
    expect(checkBeforeUpload(pdf({ pages: 1001 }), limits, room)).toMatchObject({
      reason: 'too_many_pages',
      limit: 1000,
    })
    expect(checkBeforeUpload(pdf({ pages: null }), limits, room)).toBeNull()
  })
  it('refuses when storage would overflow, and when the PDF count is reached', () => {
    expect(checkBeforeUpload(pdf(), limits, { storageBytes: 495 * MIB, documents: 3 })).toMatchObject({
      reason: 'quota',
      kind: 'storage',
    })
    expect(checkBeforeUpload(pdf(), limits, { storageBytes: 0, documents: 100 })).toMatchObject({
      reason: 'quota',
      kind: 'documents',
    })
  })
  it('skips the quota checks while usage is still loading', () =>
    expect(checkBeforeUpload(pdf(), limits, undefined)).toBeNull())
  it('checks the type before the size', () =>
    expect(checkBeforeUpload(pdf({ type: 'text/plain', name: 'a.txt', bytes: 99 * MIB }), limits, room)).toEqual({
      reason: 'type',
    }))
})

describe('limits and the full quota', () => {
  const usage = (storage: number, documents: number, plan = 'free') =>
    ({
      plan,
      limits: {
        max_storage_mb: 500,
        max_documents: 100,
        max_file_mb: 50,
        max_pages: 1000,
        max_notes: 1,
        max_note_chars: 1,
        max_note_images: 1,
        max_tags: 1,
      },
      used: { storage_bytes: storage, notes: 0, tags: 0, documents },
      resets_on: '2026-11-01',
      largest_documents: [{ id: 'd', title: 'Big', bytes: 5 }],
    }) as never
  it('falls back to the plan defaults until usage loads', () => {
    expect(limitsFromUsage(undefined)).toEqual(FALLBACK_UPLOAD_LIMITS)
    expect(limitsFromUsage(usage(0, 0))).toEqual(limits)
  })
  it('is null while there is room, and names what is full otherwise', () => {
    expect(fullQuota(undefined)).toBeNull()
    expect(fullQuota(usage(1, 1))).toBeNull()
    expect(fullQuota(usage(500 * MIB, 1))).toMatchObject({
      kind: 'storage',
      limit: 500 * MIB,
      largest_documents: [{ id: 'd' }],
    })
    expect(fullQuota(usage(1, 100))).toMatchObject({ kind: 'documents', used: 100, limit: 100 })
  })
  it('words every refusal with a way forward', () => {
    for (const refusal of [
      { reason: 'type' as const },
      { reason: 'too_large' as const, limitMb: 50, bytes: 60 * MIB },
      { reason: 'too_many_pages' as const, limit: 1000, pages: 1200 },
      { reason: 'quota' as const, kind: 'storage' as const, used: 1, limit: 1 },
      { reason: 'quota' as const, kind: 'documents' as const, used: 1, limit: 1 },
    ]) {
      const text = refusalText(refusal)
      expect(text.title.length).toBeGreaterThan(5)
      expect(text.hint.length).toBeGreaterThan(5)
    }
  })
})

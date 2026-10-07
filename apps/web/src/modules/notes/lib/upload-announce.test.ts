import { describe, expect, it } from 'vitest'

import { announceChange } from './upload-announce'
import type { UploadItem } from './upload-manager'

const item = (over: Partial<UploadItem> = {}): UploadItem => ({
  id: 'u1',
  fileName: 'tax.pdf',
  bytes: 1000,
  pages: null,
  phase: 'uploading',
  loaded: 0,
  startedAt: 0,
  ...over,
})

describe('upload announcements for the live region', () => {
  it('speaks when an upload starts', () => expect(announceChange(undefined, item())).toBe('Uploading tax.pdf.'))
  it('speaks each phase change that matters and nothing for the quiet ones', () => {
    expect(announceChange(item(), item({ phase: 'processing' }))).toBe('tax.pdf uploaded. Checking the file.')
    expect(announceChange(item(), item({ phase: 'ready' }))).toBe('tax.pdf is ready.')
    expect(announceChange(item(), item({ phase: 'duplicate' }))).toMatch(/already have tax.pdf/)
    expect(
      announceChange(
        item(),
        item({
          phase: 'failed',
          failure: { reason: 'network', message: 'Upload paused, connection lost.', retryable: true },
        }),
      ),
    ).toBe('tax.pdf: Upload paused, connection lost.')
    expect(announceChange(item({ phase: 'reserving' }), item({ phase: 'completing' }))).toBeNull()
  })
  it('speaks every quarter, not every byte', () => {
    expect(announceChange(item({ loaded: 100 }), item({ loaded: 200 }))).toBeNull()
    expect(announceChange(item({ loaded: 200 }), item({ loaded: 260 }))).toBe('tax.pdf: 25 percent uploaded.')
    expect(announceChange(item({ loaded: 510 }), item({ loaded: 740 }))).toBeNull()
  })
})

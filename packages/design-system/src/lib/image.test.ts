import { describe, expect, it } from 'vitest'

import { bytesBucket, checkImageFile, checkImageSize, MAX_FILE_BYTES } from './image'

describe('checkImageFile', () => {
  it('accepts the supported types up to 10 MB', () => {
    for (const type of ['image/jpeg', 'image/png', 'image/webp', 'image/heic']) {
      expect(checkImageFile({ type, size: 1000 })).toBeNull()
    }
    expect(checkImageFile({ type: 'image/png', size: MAX_FILE_BYTES })).toBeNull()
  })
  it('refuses other types and big files', () => {
    expect(checkImageFile({ type: 'image/gif', size: 10 })).toBe('type')
    expect(checkImageFile({ type: 'application/pdf', size: 10 })).toBe('type')
    expect(checkImageFile({ type: '', size: 10 })).toBe('type')
    expect(checkImageFile({ type: 'image/png', size: MAX_FILE_BYTES + 1 })).toBe('size')
  })
})

describe('checkImageSize', () => {
  it('needs 128 px on the short side', () => {
    expect(checkImageSize(127, 4000)).toBe('small')
    expect(checkImageSize(4000, 127)).toBe('small')
    expect(checkImageSize(128, 128)).toBeNull()
  })
})

describe('bytesBucket', () => {
  it('never reveals the exact size', () => {
    expect(bytesBucket(50_000)).toBe('lt_100kb')
    expect(bytesBucket(250_000)).toBe('100_300kb')
    expect(bytesBucket(500_000)).toBe('300_600kb')
    expect(bytesBucket(900_000)).toBe('gt_600kb')
  })
})

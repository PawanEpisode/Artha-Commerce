import { afterEach, describe, expect, it, vi } from 'vitest'

import { isDocumentPipSupported } from './pip'

afterEach(() => vi.unstubAllGlobals())

describe('isDocumentPipSupported', () => {
  it('is false during server rendering, where there is no window', () => {
    expect(isDocumentPipSupported()).toBe(false)
  })

  it('is false in a browser without the API', () => {
    vi.stubGlobal('window', {})
    expect(isDocumentPipSupported()).toBe(false)
  })

  it('is true when the API exists', () => {
    vi.stubGlobal('window', { documentPictureInPicture: {} })
    expect(isDocumentPipSupported()).toBe(true)
  })
})

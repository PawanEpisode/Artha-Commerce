import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { ATTEMPTS, type ResumableDeps, uploadInParts } from './resumable-upload'

const MB = 1024 * 1024
const hint = { document_id: 'd1', part_size: 8 * MB, parts: 3 }
const file = new Blob([new Uint8Array(20 * MB)]) // 8 + 8 + 4 MiB

function setup(over: Partial<ResumableDeps> = {}) {
  const puts: Array<{ url: string; size: number }> = []
  const deps: ResumableDeps = {
    start: vi.fn(async () => ({ part_size: 8 * MB, parts: 3, done: [] })),
    sign: vi.fn(async (_id, numbers: number[]) => ({
      parts: numbers.map((number) => ({ number, url: `u${number}` })),
    })),
    put: vi.fn(async (url: string, part: Blob, o) => {
      puts.push({ url, size: part.size })
      o.onProgress?.(part.size)
    }),
    finish: vi.fn(async () => ({ joined: 3 })),
    wait: vi.fn(async () => undefined),
    ...over,
  }
  return { deps, puts }
}

describe('uploadInParts', () => {
  it('sends every part with the right slice, reports progress up to the whole file and then joins them', async () => {
    const { deps, puts } = setup()
    const progress: number[] = []
    await uploadInParts(deps, hint, file, { onProgress: (loaded) => progress.push(loaded) })
    expect(puts.map((p) => p.size).sort((a, b) => b - a)).toEqual([8 * MB, 8 * MB, 4 * MB])
    expect(progress.at(-1)).toBe(20 * MB)
    expect(progress.every((v, i) => i === 0 || v >= 0)).toBe(true)
    expect(deps.finish).toHaveBeenCalledExactlyOnceWith('d1', [1, 2, 3])
  })

  it('skips the parts storage already holds (a retry continues where it stopped)', async () => {
    const { deps, puts } = setup({
      start: vi.fn(async () => ({
        part_size: 8 * MB,
        parts: 3,
        done: [
          { number: 1, size: 8 * MB },
          { number: 2, size: 8 * MB },
        ],
      })),
    })
    const progress: number[] = []
    await uploadInParts(deps, hint, file, { onProgress: (l) => progress.push(l) })
    expect(puts).toEqual([{ url: 'u3', size: 4 * MB }])
    expect(progress[0]).toBe(16 * MB) // starts from what is already there
  })

  it('tries a failed part again after a pause, and only that part', async () => {
    let failures = 0
    const { deps, puts } = setup({
      put: vi.fn(async (url: string, part: Blob) => {
        if (url === 'u2' && failures++ < 2) throw new ApiError(0, 'Network error during upload')
        puts.push({ url, size: part.size })
      }),
    })
    await uploadInParts(deps, hint, file)
    expect(puts.filter((p) => p.url === 'u2')).toHaveLength(1)
    expect(puts.filter((p) => p.url === 'u1')).toHaveLength(1)
    expect(deps.wait).toHaveBeenNthCalledWith(1, 1000)
    expect(deps.wait).toHaveBeenNthCalledWith(2, 2000)
  })

  it('asks for a fresh URL when the old one was refused as expired', async () => {
    let refused = false
    const { deps } = setup({
      put: vi.fn(async (url: string) => {
        if (url === 'u1' && !refused) {
          refused = true
          throw new ApiError(403, 'expired')
        }
      }),
    })
    await uploadInParts(deps, hint, file)
    expect(
      (deps.sign as ReturnType<typeof vi.fn>).mock.calls.filter(([, n]) => (n as number[]).includes(1)),
    ).toHaveLength(2)
  })

  it('gives up after the attempts run out, throws the last error and never joins', async () => {
    const down = new ApiError(0, 'Network error during upload')
    const { deps } = setup({ put: vi.fn(async () => Promise.reject(down)) })
    await expect(uploadInParts(deps, hint, file)).rejects.toBe(down)
    expect(deps.finish).not.toHaveBeenCalled()
    expect((deps.put as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThanOrEqual(ATTEMPTS)
  })

  it('does not retry a refusal that will not change', async () => {
    const refused = new ApiError(413, 'too big')
    const { deps } = setup({ put: vi.fn(async () => Promise.reject(refused)) })
    await expect(uploadInParts(deps, hint, file)).rejects.toBe(refused)
    expect(deps.wait).not.toHaveBeenCalled()
  })

  it('stops with an AbortError when cancelled', async () => {
    const controller = new AbortController()
    const { deps } = setup({
      put: vi.fn(async () => {
        controller.abort()
        throw new DOMException('Upload cancelled', 'AbortError')
      }),
    })
    await expect(uploadInParts(deps, hint, file, { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    })
    expect(deps.finish).not.toHaveBeenCalled()
  })
})

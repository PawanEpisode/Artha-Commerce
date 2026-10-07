import { afterEach, describe, expect, it, vi } from 'vitest'

import { MINI_PATH, MINI_WINDOW_FEATURES, MINI_WINDOW_NAME, openMiniWindow } from './mini-window'

afterEach(() => vi.restoreAllMocks())

describe('openMiniWindow', () => {
  it('opens the named small window and brings it to the front, so a second click finds the same one', () => {
    const focus = vi.fn()
    const open = vi.spyOn(window, 'open').mockReturnValue({ focus } as unknown as Window)
    expect(openMiniWindow()).not.toBeNull()
    expect(open).toHaveBeenCalledWith(MINI_PATH, MINI_WINDOW_NAME, MINI_WINDOW_FEATURES)
    expect(MINI_PATH).toBe('/app/focus/mini')
    expect(MINI_WINDOW_FEATURES).toBe('popup,width=320,height=220')
    expect(focus).toHaveBeenCalledOnce()
  })

  it('is null when the browser blocked the pop-up', () => {
    vi.spyOn(window, 'open').mockReturnValue(null)
    expect(openMiniWindow()).toBeNull()
  })

  it('still reports the window when the browser refuses to focus it', () => {
    vi.spyOn(window, 'open').mockReturnValue({
      focus: () => {
        throw new Error('no')
      },
    } as unknown as Window)
    expect(openMiniWindow()).not.toBeNull()
  })
})

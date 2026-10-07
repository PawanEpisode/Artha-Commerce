import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetClock, setServerTime } from '~/modules/tracker'
import { fakePipWindow, removePipStub, stubPip } from '~/test/pip-window'

import { popoutPresence, resetPopoutPresence, setPresenceTarget } from '../lib/popout-presence'
import { useDocumentPip } from './useDocumentPip'

beforeEach(() => {
  resetPopoutPresence()
  resetClock()
})
afterEach(() => {
  removePipStub()
  vi.restoreAllMocks()
  document.documentElement.removeAttribute('data-theme')
})

describe('useDocumentPip', () => {
  it('does nothing in a browser without Document Picture-in-Picture', async () => {
    const { result } = renderHook(() => useDocumentPip())
    let opened = true
    await act(async () => {
      opened = await result.current.open('pill')
    })
    expect(opened).toBe(false)
    expect(result.current.isOpen).toBe(false)
  })

  it('opens the window at the pill size, titled and themed, with a root to draw into', async () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    const win = fakePipWindow()
    const requestWindow = stubPip(win)
    const { result } = renderHook(() => useDocumentPip())
    await act(async () => {
      expect(await result.current.open('pill')).toBe(true)
    })
    expect(requestWindow).toHaveBeenCalledWith({ width: 320, height: 156 })
    expect(result.current.isOpen).toBe(true)
    expect(result.current.window).toBe(win)
    expect(win.document.title).toBe('Artha timer')
    expect(win.document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(result.current.root).toBe(win.document.getElementById('artha-popout-root'))
    expect(popoutPresence().popoutOpen).toBe(true)
  })

  it('opens at the size it is given and remembers it as the layout', async () => {
    const requestWindow = stubPip(fakePipWindow())
    const { result } = renderHook(() => useDocumentPip())
    await act(async () => void (await result.current.open('card')))
    expect(requestWindow).toHaveBeenCalledWith({ width: 320, height: 300 })
    expect(result.current.size).toBe('card')
  })

  it('stays closed when the browser refuses (no click, or no permission)', async () => {
    stubPip(new DOMException('needs a click', 'NotAllowedError'))
    const { result } = renderHook(() => useDocumentPip())
    let opened = true
    await act(async () => {
      opened = await result.current.open('pill')
    })
    expect(opened).toBe(false)
    expect(result.current.isOpen).toBe(false)
    expect(popoutPresence().popoutOpen).toBe(false)
  })

  it('asks the browser once, however many times it is opened', async () => {
    const requestWindow = stubPip(fakePipWindow())
    const { result } = renderHook(() => useDocumentPip())
    await act(async () => {
      await Promise.all([result.current.open('pill'), result.current.open('pill')])
    })
    await act(async () => void (await result.current.open('pill')))
    expect(requestWindow).toHaveBeenCalledOnce()
  })

  it('goes back to closed when the window closes itself (pagehide), and says by whom', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const onClosed = vi.fn()
    const { result } = renderHook(() => useDocumentPip({ onClosed }))
    await act(async () => void (await result.current.open('pill')))
    act(() => void win.dispatchEvent(new Event('pagehide')))
    expect(result.current.isOpen).toBe(false)
    expect(result.current.window).toBeNull()
    expect(onClosed).toHaveBeenCalledWith({ by: 'student', secondsOpen: expect.any(Number) })
    expect(popoutPresence().popoutOpen).toBe(false)
  })

  it('tells a closed tab from a closed window', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const onClosed = vi.fn()
    const { result } = renderHook(() => useDocumentPip({ onClosed }))
    await act(async () => void (await result.current.open('pill')))
    act(() => {
      window.dispatchEvent(new Event('pagehide'))
      win.dispatchEvent(new Event('pagehide'))
    })
    expect(onClosed).toHaveBeenCalledWith(expect.objectContaining({ by: 'tab_closed' }))
  })

  it('closes the window on request and reports why', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const onClosed = vi.fn()
    const { result } = renderHook(() => useDocumentPip({ onClosed }))
    await act(async () => void (await result.current.open('pill')))
    act(() => result.current.close('flag_off'))
    expect(win.close).toHaveBeenCalledOnce()
    expect(result.current.isOpen).toBe(false)
    expect(onClosed).toHaveBeenCalledOnce()
    expect(onClosed).toHaveBeenCalledWith(expect.objectContaining({ by: 'flag_off' }))
  })

  it('closes the window when the app goes away', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const { result, unmount } = renderHook(() => useDocumentPip())
    await act(async () => void (await result.current.open('pill')))
    unmount()
    expect(win.close).toHaveBeenCalledOnce()
  })

  it('counts a tap in the window as presence, after the target', async () => {
    setServerTime(new Date().toISOString())
    const win = fakePipWindow()
    stubPip(win)
    const { result } = renderHook(() => useDocumentPip())
    await act(async () => void (await result.current.open('pill')))
    setPresenceTarget(Date.now() - 1000)
    expect(popoutPresence()).toMatchObject({ pastTarget: true, tappedSinceTarget: false })
    act(() => void win.dispatchEvent(new Event('pointerdown')))
    expect(popoutPresence().tappedSinceTarget).toBe(true)
  })

  it('stops counting the window while it is hidden', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const { result } = renderHook(() => useDocumentPip())
    await act(async () => void (await result.current.open('pill')))
    vi.spyOn(win.document, 'visibilityState', 'get').mockReturnValue('hidden')
    act(() => void win.document.dispatchEvent(new Event('visibilitychange')))
    expect(popoutPresence().popoutOpen).toBe(false)
  })

  describe('resize', () => {
    it('switches the layout and reports true when the browser resized the window', async () => {
      const win = fakePipWindow()
      win.resizeTo.mockImplementation((w: number, h: number) => {
        win.innerWidth = w - 0
        win.innerHeight = h - 34
      })
      stubPip(win)
      const { result } = renderHook(() => useDocumentPip())
      await act(async () => void (await result.current.open('pill')))
      let resized = false
      await act(async () => {
        resized = await result.current.resize('card')
      })
      expect(resized).toBe(true)
      expect(result.current.size).toBe('card')
      expect(win.resizeTo).toHaveBeenCalledWith(320, 334)
    })

    it('still switches the layout when the browser keeps the size, and never closes or reopens the window', async () => {
      const win = fakePipWindow()
      const requestWindow = stubPip(win)
      const { result } = renderHook(() => useDocumentPip())
      await act(async () => void (await result.current.open('pill')))
      let resized = true
      await act(async () => {
        resized = await result.current.resize('card')
      })
      expect(resized).toBe(false)
      expect(result.current.size).toBe('card')
      expect(result.current.isOpen).toBe(true)
      expect(win.close).not.toHaveBeenCalled()
      expect(requestWindow).toHaveBeenCalledOnce()
    })
  })
})

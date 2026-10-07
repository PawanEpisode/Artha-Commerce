import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyStyles, mirrorTheme, PIP_TITLE, requestPipWindow, tryResizePip } from './pip'

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(window, 'documentPictureInPicture')
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.className = ''
  document.documentElement.style.colorScheme = ''
})

const blank = () => document.implementation.createHTMLDocument('')

describe('requestPipWindow', () => {
  it('asks for the size of the layout', async () => {
    const requestWindow = vi.fn().mockResolvedValue({})
    Object.defineProperty(window, 'documentPictureInPicture', { value: { requestWindow }, configurable: true })
    await requestPipWindow('pill')
    await requestPipWindow('card')
    expect(requestWindow).toHaveBeenNthCalledWith(1, { width: 320, height: 156 })
    expect(requestWindow).toHaveBeenNthCalledWith(2, { width: 320, height: 300 })
  })

  it('rejects where the browser has no Document Picture-in-Picture', async () => {
    await expect(requestPipWindow('pill')).rejects.toThrow(/not supported/)
  })

  it('names the window "Artha timer"', () => {
    expect(PIP_TITLE).toBe('Artha timer')
  })
})

describe('copyStyles', () => {
  it('links a sheet that has an address by its absolute address', () => {
    vi.spyOn(document, 'styleSheets', 'get').mockReturnValue([
      { href: 'https://artha.test/assets/app.css' },
    ] as unknown as StyleSheetList)
    const to = blank()
    copyStyles(document, to)
    const link = to.head.querySelector('link[rel="stylesheet"]')
    expect(link?.getAttribute('href')).toBe('https://artha.test/assets/app.css')
  })

  it('copies a sheet without an address as text', () => {
    const style = document.createElement('style')
    style.textContent = '.artha-test { color: red; }'
    document.head.appendChild(style)
    const to = blank()
    copyStyles(document, to)
    expect(to.head.querySelector('style')?.textContent).toContain('.artha-test')
    style.remove()
  })

  it('leaves out a sheet the browser will not let it read', () => {
    const locked = {
      href: null,
      get cssRules(): never {
        throw new DOMException('blocked', 'SecurityError')
      },
    }
    vi.spyOn(document, 'styleSheets', 'get').mockReturnValue([locked] as unknown as StyleSheetList)
    const to = blank()
    expect(() => copyStyles(document, to)).not.toThrow()
    expect(to.head.querySelectorAll('link, style')).toHaveLength(0)
  })
})

describe('mirrorTheme', () => {
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

  it('copies data-theme, class and color-scheme at once, then follows changes', async () => {
    const from = document.documentElement
    from.setAttribute('data-theme', 'dark')
    from.classList.add('dark')
    from.style.colorScheme = 'dark'
    const to = blank().documentElement
    const stop = mirrorTheme(from, to)
    expect(to.getAttribute('data-theme')).toBe('dark')
    expect(to.classList.contains('dark')).toBe(true)
    expect(to.style.colorScheme).toBe('dark')

    from.setAttribute('data-theme', 'reading')
    from.classList.remove('dark')
    from.style.colorScheme = 'light'
    await settle()
    expect(to.getAttribute('data-theme')).toBe('reading')
    expect(to.classList.contains('dark')).toBe(false)
    expect(to.style.colorScheme).toBe('light')

    stop()
    from.setAttribute('data-theme', 'light')
    await settle()
    expect(to.getAttribute('data-theme')).toBe('reading')
  })
})

describe('tryResizePip', () => {
  const fakeWindow = (accept: boolean) => {
    const win = { innerWidth: 320, innerHeight: 156, outerWidth: 320, outerHeight: 190, resizeTo: vi.fn() }
    win.resizeTo.mockImplementation((w: number, h: number) => {
      if (!accept) return
      win.innerWidth = w - (win.outerWidth - win.innerWidth)
      win.innerHeight = h - (win.outerHeight - win.innerHeight)
      win.outerWidth = w
      win.outerHeight = h
    })
    return win
  }

  it('asks for the inner size plus the window frame and reports success when the size changed', async () => {
    const win = fakeWindow(true)
    expect(await tryResizePip(win as unknown as Window, 'card')).toBe(true)
    expect(win.resizeTo).toHaveBeenCalledWith(320, 334)
    expect(win.innerHeight).toBe(300)
  })

  it('reports false when the browser keeps the size, so only the layout switches', async () => {
    expect(await tryResizePip(fakeWindow(false) as unknown as Window, 'card')).toBe(false)
  })

  it('reports false when resizing throws', async () => {
    const win = fakeWindow(true)
    win.resizeTo.mockImplementation(() => {
      throw new Error('no activation')
    })
    expect(await tryResizePip(win as unknown as Window, 'card')).toBe(false)
  })
})

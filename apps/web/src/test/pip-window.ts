import { vi } from 'vitest'

/** A stand-in for the Picture-in-Picture window: a real (detached) document, events, and spies for what we call. */
export function fakePipWindow() {
  const doc = document.implementation.createHTMLDocument('')
  const win = Object.assign(new EventTarget(), {
    document: doc,
    innerWidth: 320,
    innerHeight: 156,
    outerWidth: 320,
    outerHeight: 190,
    resizeTo: vi.fn(),
    setInterval: vi.fn(() => 1),
    clearInterval: vi.fn(),
    close: vi.fn(() => {
      win.dispatchEvent(new Event('pagehide'))
    }),
  })
  return win
}

export type FakePipWindow = ReturnType<typeof fakePipWindow>

/** Installs `documentPictureInPicture` on the test window and returns its `requestWindow` spy. */
export function stubPip(win: FakePipWindow | Error) {
  const requestWindow = vi.fn(() => (win instanceof Error ? Promise.reject(win) : Promise.resolve(win)))
  Object.defineProperty(window, 'documentPictureInPicture', { value: { requestWindow }, configurable: true })
  return requestWindow
}

export const removePipStub = () => Reflect.deleteProperty(window, 'documentPictureInPicture')

import { useSyncExternalStore } from 'react'

import { isDesktopBrowser, isDocumentPipSupported } from '../lib/pip'

const subscribeNever = () => () => undefined

/** False while rendering on the server and while hydrating, then what the browser says, so the two renders agree. */
export const useDocumentPipSupported = () => useSyncExternalStore(subscribeNever, isDocumentPipSupported, () => false)

/** True on a desktop or laptop (a mouse or trackpad is the main pointer); false on phones and tablets. */
export const useDesktopBrowser = () => useSyncExternalStore(subscribeNever, isDesktopBrowser, () => false)

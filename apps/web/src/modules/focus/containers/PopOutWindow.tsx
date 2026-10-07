import { type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { usePopOut } from '../hooks/usePopOut'

/**
 * Draws its children into the floating window. The children stay part of the app's React tree, so they share the
 * query cache, the heartbeat and the alerts with the page: there is no second timer, only a second place to look.
 */
export function PopOutWindow({ children }: { children: ReactNode }) {
  const { root } = usePopOut()
  return root ? createPortal(children, root) : null
}

import { useLocation, useRouter } from '@tanstack/react-router'
import { type MouseEvent, useEffect, useRef, useState } from 'react'

import { BellButton, INBOX_PATH } from '../components/BellButton'
import { useBellCount } from '../hooks/useInbox'
import { announceChange, isModifiedClick } from '../lib/inbox'

/**
 * The inbox bell for the header (signed-in students only; the caller decides that). It polls the unread count, and
 * renders nothing while notifications are off for this student, so the header looks as it did before.
 */
export function BellContainer() {
  const router = useRouter()
  const onInbox = useLocation({ select: (location) => location.pathname.replace(/\/+$/, '') === INBOX_PATH })
  const { unread, off } = useBellCount()
  const previous = useRef<number | null>(null)
  const [announcement, setAnnouncement] = useState<string | null>(null)

  useEffect(() => {
    if (unread === null) return
    setAnnouncement(announceChange(previous.current, unread))
    previous.current = unread
  }, [unread])

  if (off) return null

  const open = (event: MouseEvent<HTMLAnchorElement>) => {
    if (isModifiedClick(event)) return
    event.preventDefault()
    router.history.push(INBOX_PATH)
  }

  return <BellButton unread={unread} announcement={announcement} current={onInbox} onOpen={open} />
}

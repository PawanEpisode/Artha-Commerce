import { Button, PictureInPicture2, Undo2 } from '@artha/design-system'

import { type PopOutSource, type PopOutTimerKind, usePopOut } from '../hooks/usePopOut'
import type { PopOutSize } from '../lib/types'

interface Props {
  source: PopOutSource
  timer: PopOutTimerKind
  /** The size remembered on the account; the window opens this way. */
  size?: PopOutSize
}

/**
 * Pop out the timer, or bring it back when it is already out. It renders nothing where no window is offered (the
 * `floating_timer` flag off, signed out, or not a desktop browser); without Document Picture-in-Picture it opens the
 * small separate window instead. The click opens the window first and
 * only then does anything else, which is what the browser requires.
 */
export function PopOutButton({ source, timer, size = 'pill' }: Props) {
  const pop = usePopOut()
  // Where only the separate window exists, a second press brings the same window forward, so there is no Bring back.
  if (!pop.available && !pop.fallback) return null
  return pop.isOpen ? (
    <Button
      size="icon"
      variant="outline"
      aria-label="Bring the timer back"
      title="Bring the timer back"
      onClick={pop.close}
    >
      <Undo2 aria-hidden />
    </Button>
  ) : (
    <Button
      size="icon"
      variant="outline"
      aria-label="Pop out the timer"
      title="Pop out the timer"
      onClick={() => void pop.open(size, { source, timer })}
    >
      <PictureInPicture2 aria-hidden />
    </Button>
  )
}

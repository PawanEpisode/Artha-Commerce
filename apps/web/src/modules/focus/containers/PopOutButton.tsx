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
 * Pop out the timer, or bring it back when it is already out. It renders nothing where the window is not offered (no
 * Document Picture-in-Picture, the `floating_timer` flag off, signed out). The click opens the window first and
 * only then does anything else, which is what the browser requires.
 */
export function PopOutButton({ source, timer, size = 'pill' }: Props) {
  const pop = usePopOut()
  if (!pop.available) return null
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

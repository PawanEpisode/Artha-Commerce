import { fireEvent, render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PenCanvas } from './PenCanvas'

/** jsdom has no PointerEvent: a MouseEvent with the pointer fields the canvas reads. */
function pointer(
  type: string,
  init: {
    pointerType: string
    pointerId?: number
    x: number
    y: number
    buttons?: number
    contact?: number
    t?: number
  },
) {
  const event = new MouseEvent(type, {
    bubbles: true,
    cancelable: true,
    clientX: init.x,
    clientY: init.y,
    buttons: init.buttons ?? 1,
  })
  Object.defineProperties(event, {
    pointerType: { value: init.pointerType },
    pointerId: { value: init.pointerId ?? 1 },
    width: { value: init.contact ?? 1 },
    height: { value: init.contact ?? 1 },
  })
  return event
}

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 600, 800))
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => setTimeout(() => cb(0), 0) as unknown as number)
})

const setup = (fingerDraws = false) => {
  const onStroke = vi.fn()
  const view = render(
    <PenCanvas
      width={600}
      height={800}
      color="i1"
      strokeWidth={0.0035}
      fingerDraws={fingerDraws}
      onStroke={onStroke}
    />,
  )
  const surface = view.container.querySelector('[data-slot="pen-canvas"]') as HTMLElement
  return { onStroke, surface }
}

describe('PenCanvas with simulated pointers', () => {
  it('a stylus draws: the finished stroke arrives in the stored frame (0 to 1)', () => {
    const { onStroke, surface } = setup()
    fireEvent(surface, pointer('pointerdown', { pointerType: 'pen', x: 60, y: 80 }))
    fireEvent(surface, pointer('pointermove', { pointerType: 'pen', x: 300, y: 400 }))
    fireEvent(surface, pointer('pointermove', { pointerType: 'pen', x: 540, y: 720 }))
    fireEvent(surface, pointer('pointerup', { pointerType: 'pen', x: 540, y: 720, buttons: 0 }))
    expect(onStroke).toHaveBeenCalledTimes(1)
    const [points, width] = onStroke.mock.calls[0] as [Array<{ x: number; y: number }>, number]
    expect(width).toBe(0.0035)
    expect(points[0]).toMatchObject({ x: 0.1, y: 0.1 })
    expect(points.at(-1)).toMatchObject({ x: 0.9, y: 0.9 })
  })

  it('a finger scrolls: nothing is drawn and the page keeps the gesture', () => {
    const { onStroke, surface } = setup()
    const down = pointer('pointerdown', { pointerType: 'touch', x: 60, y: 80 })
    fireEvent(surface, down)
    fireEvent(surface, pointer('pointermove', { pointerType: 'touch', x: 60, y: 300 }))
    fireEvent(surface, pointer('pointerup', { pointerType: 'touch', x: 60, y: 300, buttons: 0 }))
    expect(onStroke).not.toHaveBeenCalled()
    expect(down.defaultPrevented).toBe(false)
  })

  it('a palm resting beside the stylus is ignored, and the stylus stroke is unharmed', () => {
    const { onStroke, surface } = setup(true)
    fireEvent(surface, pointer('pointerdown', { pointerType: 'pen', pointerId: 1, x: 60, y: 80 }))
    const palm = pointer('pointerdown', { pointerType: 'touch', pointerId: 2, x: 300, y: 500, contact: 80 })
    fireEvent(surface, palm)
    fireEvent(surface, pointer('pointermove', { pointerType: 'touch', pointerId: 2, x: 320, y: 520, contact: 80 }))
    fireEvent(surface, pointer('pointermove', { pointerType: 'pen', pointerId: 1, x: 200, y: 200 }))
    fireEvent(surface, pointer('pointerup', { pointerType: 'pen', pointerId: 1, x: 200, y: 200, buttons: 0 }))
    expect(palm.defaultPrevented).toBe(true)
    expect(onStroke).toHaveBeenCalledTimes(1)
  })

  it('with "finger draws" on, one finger draws', () => {
    const { onStroke, surface } = setup(true)
    fireEvent(surface, pointer('pointerdown', { pointerType: 'touch', x: 60, y: 80 }))
    fireEvent(surface, pointer('pointermove', { pointerType: 'touch', x: 160, y: 180 }))
    fireEvent(surface, pointer('pointerup', { pointerType: 'touch', x: 160, y: 180, buttons: 0 }))
    expect(onStroke).toHaveBeenCalledTimes(1)
  })

  it('a stylus held near the glass stops the page panning under it (touch-action: none)', () => {
    const { surface } = setup()
    fireEvent(surface, pointer('pointermove', { pointerType: 'pen', x: 10, y: 10, buttons: 0 }))
    expect(surface.style.touchAction).toBe('none')
  })
})

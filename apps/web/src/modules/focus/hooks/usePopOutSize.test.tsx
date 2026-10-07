import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ mutate: vi.fn() }))
vi.mock('./useFocusSettings', () => ({ useSaveFocusSettings: () => ({ mutate: state.mutate }) }))

import { type PopOutApi, PopOutContext } from './usePopOut'
import { usePopOutSize } from './usePopOutSize'

const api = (size: 'pill' | 'card', resize = vi.fn().mockResolvedValue(true)): PopOutApi => ({
  available: true,
  isOpen: true,
  window: null,
  root: null,
  size,
  open: vi.fn(),
  close: vi.fn(),
  resize,
})
const wrap = (value: PopOutApi) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <PopOutContext.Provider value={value}>{children}</PopOutContext.Provider>
  }

describe('usePopOutSize', () => {
  it('switches the pill to the card, asks for the new window size and writes popout_size', async () => {
    state.mutate.mockClear()
    const value = api('pill')
    const { result } = renderHook(() => usePopOutSize(), { wrapper: wrap(value) })
    await act(async () => result.current.toggle())
    expect(value.resize).toHaveBeenCalledWith('card')
    expect(state.mutate).toHaveBeenCalledWith({ popout_size: 'card' })
  })

  it('switches the card back to the pill', async () => {
    state.mutate.mockClear()
    const value = api('card')
    const { result } = renderHook(() => usePopOutSize(), { wrapper: wrap(value) })
    expect(result.current.size).toBe('card')
    await act(async () => result.current.toggle())
    expect(value.resize).toHaveBeenCalledWith('pill')
    expect(state.mutate).toHaveBeenCalledWith({ popout_size: 'pill' })
  })
})

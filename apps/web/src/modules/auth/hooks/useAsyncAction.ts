import { useCallback, useState } from 'react'

import type { AuthResult } from '../lib/auth-api'

type ActionState = { status: 'idle' | 'pending' | 'success' | 'error'; error?: string }

/** Tracks one async auth call (idle, pending, success, error) so every form handles it the same way. */
export function useAsyncAction() {
  const [state, setState] = useState<ActionState>({ status: 'idle' })

  const run = useCallback(async (call: () => Promise<AuthResult>) => {
    setState({ status: 'pending' })
    const result = await call()
    setState(result.error ? { status: 'error', error: result.error } : { status: 'success' })
    return result
  }, [])

  const reset = useCallback(() => setState({ status: 'idle' }), [])

  return { ...state, pending: state.status === 'pending', run, reset }
}

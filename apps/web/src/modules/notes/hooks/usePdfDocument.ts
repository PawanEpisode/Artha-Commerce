import { useCallback, useEffect, useRef, useState } from 'react'

import {
  loadPdfjsEngine,
  type PasswordReason,
  type PdfDocumentHandle,
  type PdfEngine,
  PdfEngineError,
} from '../lib/pdf-engine'

export type OpenState =
  | { phase: 'idle' }
  | { phase: 'opening'; progress: { loaded: number; total: number } | null }
  | { phase: 'ready'; handle: PdfDocumentHandle }
  | { phase: 'error'; error: PdfEngineError }
  /** The student cancelled the password prompt. */
  | { phase: 'cancelled' }

export interface PasswordPrompt {
  reason: PasswordReason
  attempt: number
}

export interface UsePdfDocumentOptions {
  /** Test seam; the app uses pdf.js. */
  engine?: PdfEngine
  /** False until the document record has a file URL. */
  enabled: boolean
  /** The current signed URL and a way to get a fresh one (the file's URL expires after four hours). */
  getUrl: () => string
  refreshUrl: () => Promise<string>
}

/**
 * Opens the file with the engine and owns its lifetime: destroyed on unmount, on retry and when the URL provider changes
 * identity never matters (it is read through refs). A password request pauses the open and surfaces as `prompt`; answer it
 * with `submitPassword` or `cancelPassword`. The password goes straight to the engine and is not kept here.
 */
export function usePdfDocument({ engine, enabled, getUrl, refreshUrl }: UsePdfDocumentOptions) {
  const [state, setState] = useState<OpenState>({
    phase: enabled ? 'opening' : 'idle',
    ...(enabled ? { progress: null } : {}),
  } as OpenState)
  const [prompt, setPrompt] = useState<PasswordPrompt | null>(null)
  const [attempt, setAttempt] = useState(0)
  const answer = useRef<((password: string | null) => void) | null>(null)
  const urlRef = useRef({ getUrl, refreshUrl })
  urlRef.current = { getUrl, refreshUrl }

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    let handle: PdfDocumentHandle | null = null
    let unsubscribe: (() => void) | undefined
    setState({ phase: 'opening', progress: null })
    void (async () => {
      try {
        const impl = engine ?? (await loadPdfjsEngine())
        const opened = await impl.open({
          url: { get: () => urlRef.current.getUrl(), refresh: () => urlRef.current.refreshUrl() },
          requestPassword: (reason, tries) =>
            new Promise<string | null>((resolve) => {
              answer.current = resolve
              setPrompt({ reason, attempt: tries })
            }),
          onProgress: (loaded, total) => setState({ phase: 'opening', progress: { loaded, total } }),
          signal: controller.signal,
        })
        if (controller.signal.aborted) {
          void opened.destroy()
          return
        }
        handle = opened
        unsubscribe = opened.onFatal((error) => setState({ phase: 'error', error }))
        setPrompt(null)
        setState({ phase: 'ready', handle: opened })
      } catch (error) {
        if (controller.signal.aborted) return
        setPrompt(null)
        if (error instanceof PdfEngineError && error.code === 'password_cancelled') setState({ phase: 'cancelled' })
        else if (error instanceof PdfEngineError && error.code === 'aborted') return
        else
          setState({ phase: 'error', error: error instanceof PdfEngineError ? error : new PdfEngineError('unknown') })
      }
    })()
    return () => {
      controller.abort()
      unsubscribe?.()
      answer.current?.(null)
      answer.current = null
      void handle?.destroy()
    }
  }, [engine, enabled, attempt])

  const submitPassword = useCallback((password: string) => {
    const resolve = answer.current
    answer.current = null
    resolve?.(password)
  }, [])
  const cancelPassword = useCallback(() => {
    const resolve = answer.current
    answer.current = null
    resolve?.(null)
  }, [])
  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { state, prompt, submitPassword, cancelPassword, retry }
}

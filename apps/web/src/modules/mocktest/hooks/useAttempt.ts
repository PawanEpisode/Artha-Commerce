import { useCallback, useEffect, useRef, useState } from 'react'

import {
  acceptInstructions as apiAcceptInstructions,
  acquireLease,
  closeSection as apiCloseSection,
  fetchAttemptState,
  heartbeat,
  saveAnswers,
  startWriting as apiStartWriting,
  submitAttempt as apiSubmitAttempt,
} from '../lib/api'
import type { AttemptPhase, AttemptResult, AttemptState } from '../lib/types'

export function useAttempt(attemptId: string) {
  const [attempt, setAttempt] = useState<AttemptState | null>(null)
  const [currentPosition, setCurrentPosition] = useState(1)
  const [remainingMs, setRemainingMs] = useState(0)
  const [sectionRemainingMs, setSectionRemainingMs] = useState(0)
  const [activeSectionKey, setActiveSectionKey] = useState<string | null>(null)
  const [phase, setPhase] = useState<AttemptPhase>('instructions')

  // Answers & flags keyed by position
  const [answers, setAnswers] = useState<Record<number, unknown>>({})
  const [flags, setFlags] = useState<Record<number, boolean>>({})
  const [visitedPositions, setVisitedPositions] = useState<Set<number>>(new Set([1]))

  const [leaseEpoch, setLeaseEpoch] = useState(1)
  const [hasLeaseConflict, setHasLeaseConflict] = useState(false)
  const [leaseConflictLabel, setLeaseConflictLabel] = useState<string>('')

  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionResult, setSubmissionResult] = useState<AttemptResult | null>(null)
  const [error, setError] = useState<Error | null>(null)

  const tabIdRef = useRef(crypto.randomUUID())
  const dirtyPositionsRef = useRef<Set<number>>(new Set())

  // 1. Initial Load & Lease Acquisition
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)

    fetchAttemptState(attemptId)
      .then(async (state) => {
        if (cancelled) return
        setAttempt(state)
        setPhase(state.phase)
        setLeaseEpoch(state.lease_epoch)

        // Try acquiring lease
        try {
          const lease = await acquireLease(attemptId, tabIdRef.current, 'Active Browser Tab')
          setLeaseEpoch(lease.epoch)
          setHasLeaseConflict(!lease.held_by_me)
        } catch (e: unknown) {
          const errObj = e as { status?: number }
          if (errObj.status === 409) {
            setHasLeaseConflict(true)
          }
        }

        setIsLoading(false)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [attemptId])

  // 2. Local Clock Tick (every second)
  useEffect(() => {
    if (phase !== 'reading' && phase !== 'writing') return

    const interval = setInterval(() => {
      setRemainingMs((prev) => Math.max(0, prev - 1000))
      setSectionRemainingMs((prev) => Math.max(0, prev - 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [phase])

  // 3. Autosave dirty answers
  const flushDirtyAnswers = useCallback(async () => {
    if (dirtyPositionsRef.current.size === 0) return
    const positions = Array.from(dirtyPositionsRef.current)
    dirtyPositionsRef.current.clear()

    const payload = positions.map((pos) => ({
      position: pos,
      answer: answers[pos],
      flags: { marked_for_review: flags[pos] || false },
    }))

    try {
      await saveAnswers(attemptId, leaseEpoch, payload)
    } catch (err: unknown) {
      const errObj = err as { status?: number; message?: string }
      if (errObj.status === 409) {
        setHasLeaseConflict(true)
        setLeaseConflictLabel(errObj.message || 'Another browser tab is active')
      }
    }
  }, [attemptId, leaseEpoch, answers, flags])

  // Submit Attempt
  const handleSubmit = useCallback(async () => {
    await flushDirtyAnswers()
    setIsSubmitting(true)
    try {
      const result = await apiSubmitAttempt(attemptId, leaseEpoch)
      setSubmissionResult(result)
      setPhase('done')
      setIsSubmitting(false)
      return result
    } catch (err: unknown) {
      setIsSubmitting(false)
      setError(err instanceof Error ? err : new Error(String(err)))
      throw err
    }
  }, [attemptId, leaseEpoch, flushDirtyAnswers])

  // 4. Heartbeat & Clock Sync (every 10 seconds)
  useEffect(() => {
    if (phase !== 'reading' && phase !== 'writing') return
    if (hasLeaseConflict) return

    const doHeartbeat = async () => {
      try {
        const sync = await heartbeat(attemptId, leaseEpoch, currentPosition)
        setRemainingMs(sync.remaining_ms)
        setSectionRemainingMs(sync.section_remaining_ms)
        setActiveSectionKey(sync.active_section_key)
        setPhase(sync.phase)

        if (sync.auto_submit_due) {
          void handleSubmit()
        }
      } catch (err: unknown) {
        const errObj = err as { status?: number; message?: string }
        if (errObj.status === 409) {
          setHasLeaseConflict(true)
          setLeaseConflictLabel(errObj.message || 'Another browser tab is active')
        }
      }
    }

    void doHeartbeat()
    const interval = setInterval(doHeartbeat, 10000)
    return () => clearInterval(interval)
  }, [attemptId, leaseEpoch, currentPosition, phase, hasLeaseConflict, handleSubmit])

  // Set answer for current position
  const setAnswer = useCallback((position: number, answerVal: unknown) => {
    setAnswers((prev) => ({ ...prev, [position]: answerVal }))
    dirtyPositionsRef.current.add(position)
  }, [])

  // Toggle mark for review
  const toggleFlag = useCallback((position: number) => {
    setFlags((prev) => {
      const nextVal = !prev[position]
      dirtyPositionsRef.current.add(position)
      return { ...prev, [position]: nextVal }
    })
  }, [])

  // Navigate to position
  const goToPosition = useCallback(
    (pos: number) => {
      void flushDirtyAnswers()
      setCurrentPosition(pos)
      setVisitedPositions((prev) => new Set([...prev, pos]))
    },
    [flushDirtyAnswers],
  )

  // Accept Instructions
  const handleAcceptInstructions = useCallback(async () => {
    try {
      const nextState = await apiAcceptInstructions(attemptId)
      setAttempt(nextState)
      setPhase(nextState.phase)
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)))
    }
  }, [attemptId])

  // Start Writing (skip reading)
  const handleStartWriting = useCallback(async () => {
    try {
      const nextState = await apiStartWriting(attemptId)
      setAttempt(nextState)
      setPhase(nextState.phase)
    } catch (err: unknown) {
      setError(err instanceof Error ? err : new Error(String(err)))
    }
  }, [attemptId])

  // Close Section
  const handleCloseSection = useCallback(
    async (sectionKey: string) => {
      await flushDirtyAnswers()
      try {
        const res = await apiCloseSection(attemptId, sectionKey, leaseEpoch)
        // Refresh attempt state
        const nextState = await fetchAttemptState(attemptId)
        setAttempt(nextState)
        if (res.next_section) {
          setActiveSectionKey(res.next_section)
          // Find first question in next section
          const nextItem = nextState.layout.find((l) => l.section === res.next_section)
          if (nextItem) {
            goToPosition(nextItem.pos)
          }
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err : new Error(String(err)))
      }
    },
    [attemptId, leaseEpoch, flushDirtyAnswers, goToPosition],
  )

  // Re-acquire lease
  const handleTakeOverLease = useCallback(async () => {
    try {
      const lease = await acquireLease(attemptId, tabIdRef.current, 'Active Browser Tab')
      setLeaseEpoch(lease.epoch)
      setHasLeaseConflict(!lease.held_by_me)
    } catch {
      setHasLeaseConflict(true)
    }
  }, [attemptId])

  return {
    attempt,
    phase,
    currentPosition,
    remainingMs,
    sectionRemainingMs,
    activeSectionKey,
    answers,
    flags,
    visitedPositions,
    leaseEpoch,
    hasLeaseConflict,
    leaseConflictLabel,
    isLoading,
    isSubmitting,
    submissionResult,
    error,
    setAnswer,
    toggleFlag,
    goToPosition,
    handleAcceptInstructions,
    handleStartWriting,
    handleCloseSection,
    handleSubmit,
    handleTakeOverLease,
  }
}

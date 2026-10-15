import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  TextField,
  toast,
} from '@artha/design-system'
import { useState } from 'react'

import { logExternalScore } from '../lib/api'
import type { McqSetCard } from '../lib/types'

interface ExternalLogDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  set: McqSetCard | null
  onSuccess?: () => void
}

export function ExternalLogDialog({ open, onOpenChange, set, onSuccess }: ExternalLogDialogProps) {
  const [score, setScore] = useState('')
  const [maxScore, setMaxScore] = useState(set?.question_count ? String(set.question_count * 2) : '30')
  const [takenOn, setTakenOn] = useState(new Date().toISOString().split('T')[0])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!set) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!set) return
    setError(null)

    const numScore = parseFloat(score)
    const numMax = parseFloat(maxScore)

    if (isNaN(numScore) || numScore < 0) {
      setError('Please enter a valid non-negative score.')
      return
    }
    if (isNaN(numMax) || numMax <= 0) {
      setError('Please enter a valid max score greater than 0.')
      return
    }
    if (numScore > numMax) {
      setError('Score cannot exceed maximum score.')
      return
    }

    try {
      setIsSubmitting(true)
      const res = await logExternalScore({
        set_id: set.id,
        score: numScore,
        max_score: numMax,
        taken_on: takenOn,
      })
      toast.success(`Score logged: ${numScore}/${numMax} (${res.percentage}%).`)
      onOpenChange(false)
      onSuccess?.()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to log score. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>Log Offline / External Score</DialogTitle>
        <DialogDescription>
          Record your score from solving <span className="font-semibold text-foreground">{set.title}</span> in an
          offline test or ICMAI physical booklet.
        </DialogDescription>

        {error && (
          <Alert variant="error" className="mt-2 text-xs">
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="Your Score"
              type="number"
              step="0.5"
              min="0"
              placeholder="24"
              value={score}
              onChange={(e) => setScore(e.target.value)}
              required
            />
            <TextField
              label="Max Marks"
              type="number"
              step="0.5"
              min="1"
              placeholder="30"
              value={maxScore}
              onChange={(e) => setMaxScore(e.target.value)}
              required
            />
          </div>

          <TextField
            label="Date Completed"
            type="date"
            value={takenOn}
            onChange={(e) => setTakenOn(e.target.value)}
            required
          />

          <div className="flex justify-end gap-2 border-t pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : 'Save Score'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

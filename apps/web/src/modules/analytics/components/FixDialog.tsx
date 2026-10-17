import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'

import { useBuildFixSet } from '../hooks/useAnalytics'
import type { WeakTopicItem } from '../lib/types'

interface FixDialogProps {
  topic: WeakTopicItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FixDialog({ topic, open, onOpenChange }: FixDialogProps) {
  const navigate = useNavigate()
  const { mutate: buildFix, isPending, error } = useBuildFixSet()

  if (!topic) return null

  const handleStartFix = () => {
    buildFix(
      { topic_id: topic.topic_id, limit: 10 },
      {
        onSuccess: (data) => {
          onOpenChange(false)
          navigate({ to: `/app/practice/session/${data.session_id}` })
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Launch Targeted Drill</DialogTitle>
          <DialogDescription>
            Targeted drill session focused on addressing errors in <strong>{topic.topic_name}</strong>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          <div className="bg-surface-muted space-y-1.5 rounded-md border p-3 text-xs">
            <div className="flex justify-between">
              <span className="text-text-subtle">Chapter:</span>
              <span className="text-text font-medium">{topic.chapter_name || 'Chapter'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-subtle">Recent Accuracy:</span>
              <span className="font-semibold text-warning">
                {topic.accuracy_pct ?? Math.round((topic.accuracy ?? 0) * 100)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-subtle">Recorded Mistakes:</span>
              <span className="text-danger font-medium">{topic.mistakes_count ?? 0}</span>
            </div>
          </div>

          <p className="text-text-subtle text-xs">
            This creates an untimed 10-question practice drill prioritizing questions you previously got wrong or missed
            in this topic.
          </p>

          {error && (
            <Alert variant="error">{error instanceof Error ? error.message : 'Could not launch fix session.'}</Alert>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button variant="default" onClick={handleStartFix} loading={isPending}>
              Start Practice Session
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

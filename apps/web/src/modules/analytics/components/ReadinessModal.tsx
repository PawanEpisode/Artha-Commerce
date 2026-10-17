import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  ProgressBar,
} from '@artha/design-system'

import type { ReadinessData } from '../lib/types'

interface ReadinessModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  readiness?: ReadinessData
}

export function ReadinessModal({ open, onOpenChange, readiness }: ReadinessModalProps) {
  if (!readiness) return null

  const { state, score, half_width, confidence, label, components, levers, missing_gates } = readiness

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>Exam Readiness Engine</span>
            {typeof score === 'number' && (
              <Badge variant={confidence === 'high' ? 'accent' : 'outline'}>
                {score}/100 {confidence ? `(${confidence} confidence)` : ''}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Multi-factor readiness calculation across accuracy, syllabus breadth, coverage, retention, and speed.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-2">
          {/* Status summary */}
          <div className="bg-surface-muted space-y-2 rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <span className="text-text-subtle text-sm font-medium">Evaluation State</span>
              <span className="text-text text-sm font-semibold capitalize">{state}</span>
            </div>
            {typeof score === 'number' && typeof half_width === 'number' && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-subtle">Estimated Range</span>
                <span className="text-text font-medium">
                  {Math.max(0, Math.round(score - half_width))} – {Math.min(100, Math.round(score + half_width))}
                  <span className="text-text-subtle ml-1 text-xs">(±{half_width})</span>
                </span>
              </div>
            )}
            {label && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-subtle">Readiness Rating</span>
                <span className="font-semibold text-primary">{label}</span>
              </div>
            )}
          </div>

          {/* Missing Gates checklist if any */}
          {missing_gates.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-text text-sm font-semibold">Requirements to reach full confidence:</h4>
              <ul className="text-text-subtle space-y-1.5 text-xs">
                {missing_gates.map((gate, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="font-bold text-warning">•</span>
                    <span>{gate}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Component breakdown */}
          <div className="space-y-3">
            <h4 className="text-text text-sm font-semibold">Score Component Breakdown</h4>
            <div className="space-y-3">
              {components.map((c) => (
                <div key={c.key} className="bg-surface space-y-1.5 rounded-md border p-3">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-text font-semibold">{c.label}</span>
                      <span className="text-text-subtle">({Math.round(c.weight * 100)}% weight)</span>
                    </div>
                    <span className="text-text font-medium">
                      {c.available
                        ? `${Math.round(c.value * 100)}% (${typeof c.points === 'number' ? c.points.toFixed(1) : '0.0'} pts)`
                        : 'Not yet available'}
                    </span>
                  </div>
                  <ProgressBar value={c.available ? c.value * 100 : 0} label={`${c.label} progress`} size="sm" />
                </div>
              ))}
            </div>
          </div>

          {/* Levers to improve */}
          {levers.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-text text-sm font-semibold">Highest Impact Improvement Levers</h4>
              <div className="space-y-2">
                {levers.map((lever, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md border border-primary/20 bg-primary/5 p-3 text-xs"
                  >
                    <div>
                      <span className="text-text font-semibold capitalize">{lever.action}: </span>
                      <span className="text-text-subtle">
                        {lever.target_name || lever.target_id || 'Core Syllabus'}
                      </span>
                    </div>
                    <Badge variant="accent">
                      +{typeof lever.impact_points === 'number' ? lever.impact_points.toFixed(1) : '0.0'} pts
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

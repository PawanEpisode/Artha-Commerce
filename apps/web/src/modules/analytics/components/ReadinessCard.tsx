import { Badge, Button, Card, Skeleton } from '@artha/design-system'
import * as React from 'react'

import type { ReadinessData } from '../lib/types'
import { ReadinessModal } from './ReadinessModal'

interface ReadinessCardProps {
  data?: ReadinessData
  isLoading?: boolean
}

export function ReadinessCard({ data, isLoading }: ReadinessCardProps) {
  const [modalOpen, setModalOpen] = React.useState(false)

  if (isLoading || !data) {
    return <Skeleton className="h-44 w-full rounded-xl" />
  }

  const { state, score, half_width, confidence, label, levers } = data

  const renderBadge = () => {
    switch (state) {
      case 'ready':
        return <Badge variant={confidence === 'high' ? 'accent' : 'outline'}>{label || 'Ready'}</Badge>
      case 'early':
        return <Badge variant="outline">Early estimate</Badge>
      case 'sparse':
        return <Badge variant="highlight">Sparse data</Badge>
      case 'stale':
        return <Badge variant="outline">Stale data</Badge>
      default:
        return <Badge variant="default">Not started</Badge>
    }
  }

  return (
    <>
      <Card className="flex flex-col justify-between gap-4 p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-text text-base font-semibold">Exam Readiness Score</h3>
              {renderBadge()}
            </div>
            <p className="text-text-subtle mt-0.5 text-xs">
              Empirical Bayesian composite benchmarked to ICMAI exam standard
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => setModalOpen(true)}>
            View Breakdown
          </Button>
        </div>

        <div className="grid grid-cols-1 items-center gap-4 md:grid-cols-3">
          <div className="flex items-baseline gap-3">
            <span className="text-text text-4xl font-extrabold tracking-tight">
              {typeof score === 'number' ? score.toFixed(1) : '—'}
            </span>
            <span className="text-text-subtle text-sm font-medium">/ 100</span>
            {typeof half_width === 'number' && (
              <span className="text-text-subtle text-xs">(±{half_width.toFixed(1)} band)</span>
            )}
          </div>

          <div className="space-y-1.5 md:col-span-2">
            <span className="text-text text-xs font-semibold">Top Actionable Improvement:</span>
            {levers && levers.length > 0 && levers[0] ? (
              <div className="text-text-subtle bg-surface-muted flex items-center justify-between rounded border p-2 text-xs">
                <span>
                  <strong className="text-text capitalize">{levers[0].action}: </strong>
                  {levers[0].target_name || levers[0].target_id || 'Core questions'}
                </span>
                <span className="font-semibold text-primary">
                  +{typeof levers[0].impact_points === 'number' ? levers[0].impact_points.toFixed(1) : '0.0'} pts
                </span>
              </div>
            ) : (
              <p className="text-text-subtle text-xs">
                Complete more varied chapter practice to unlock personalized score levers.
              </p>
            )}
          </div>
        </div>
      </Card>

      <ReadinessModal open={modalOpen} onOpenChange={setModalOpen} readiness={data} />
    </>
  )
}

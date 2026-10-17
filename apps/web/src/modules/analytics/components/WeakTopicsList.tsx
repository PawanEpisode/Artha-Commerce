import { Badge, Button, Card, Skeleton } from '@artha/design-system'
import * as React from 'react'

import type { WeakTopicItem, WeakTopicsData } from '../lib/types'
import { FixDialog } from './FixDialog'

interface WeakTopicsListProps {
  data?: WeakTopicsData
  isLoading?: boolean
}

export function WeakTopicsList({ data, isLoading }: WeakTopicsListProps) {
  const [selectedTopic, setSelectedTopic] = React.useState<WeakTopicItem | null>(null)
  const [dialogOpen, setDialogOpen] = React.useState(false)

  const handleFixClick = (topic: WeakTopicItem) => {
    setSelectedTopic(topic)
    setDialogOpen(true)
  }

  if (isLoading) {
    return (
      <Card className="space-y-3 p-5">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </Card>
    )
  }

  const items = data?.items ?? []

  return (
    <>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-text text-base font-semibold">Priority Improvement Concepts</h3>
            <p className="text-text-subtle text-xs">Concepts with lower shrunk accuracy or high repeat mistakes</p>
          </div>
          <Badge variant="outline">{items.length} detected</Badge>
        </div>

        {items.length === 0 ? (
          <div className="text-text-subtle py-6 text-center text-xs">
            No weak topics detected yet! Keep practicing to see targeted recommendations.
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((topic) => (
              <div
                key={topic.topic_id}
                className="bg-surface-muted/50 hover:bg-surface-muted flex flex-col justify-between gap-2 rounded-lg border p-3 transition sm:flex-row sm:items-center"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-text text-sm font-semibold">{topic.topic_name}</span>
                    <Badge variant="highlight">
                      {topic.accuracy_pct ?? Math.round((topic.accuracy ?? 0) * 100)}% acc
                    </Badge>
                    {typeof topic.mistakes_count === 'number' && topic.mistakes_count > 0 && (
                      <span className="text-danger text-xs font-medium">
                        {topic.mistakes_count} {topic.mistakes_count === 1 ? 'mistake' : 'mistakes'}
                      </span>
                    )}
                  </div>
                  <p className="text-text-subtle text-xs">
                    {topic.chapter_name || 'Chapter'} • {topic.answered} questions attempted
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  className="shrink-0 text-xs"
                  onClick={() => handleFixClick(topic)}
                >
                  Fix This Drill
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <FixDialog topic={selectedTopic} open={dialogOpen} onOpenChange={setDialogOpen} />
    </>
  )
}

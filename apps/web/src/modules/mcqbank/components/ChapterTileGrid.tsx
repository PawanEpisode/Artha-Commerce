import { Badge, Button, Card, Play, ProgressBar } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { ChapterTile } from '../lib/types'

interface ChapterTileGridProps {
  chapters: ChapterTile[]
  subjectKey: string
  onQuickPractice?: (chapterId: string) => void
  isStarting?: boolean
}

export function ChapterTileGrid({ chapters, subjectKey, onQuickPractice, isStarting }: ChapterTileGridProps) {
  if (chapters.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
        No chapters found for this subject.
      </div>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {chapters.map((ch) => {
        const attempted = ch.available - ch.unseen
        const progressPct = ch.available > 0 ? Math.round((attempted / ch.available) * 100) : 0

        return (
          <Card key={ch.chapter_id} className="flex flex-col justify-between p-5 transition-shadow hover:shadow-md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                {ch.section ? (
                  <Badge variant="outline" className="text-xs">
                    {ch.section}
                  </Badge>
                ) : (
                  <span />
                )}
                <span className="text-xs text-muted-foreground">{ch.available} MCQs</span>
              </div>

              <div>
                <Link
                  to="/app/mcq/subjects/$subject"
                  params={{ subject: subjectKey }}
                  className="line-clamp-2 font-medium text-foreground transition-colors hover:text-primary"
                >
                  {ch.name}
                </Link>
              </div>

              <div className="space-y-1.5 pt-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Coverage ({progressPct}%)</span>
                  {ch.accuracy_recent !== null ? (
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                      {ch.accuracy_recent}% acc.
                    </span>
                  ) : (
                    <span>Not attempted</span>
                  )}
                </div>
                <ProgressBar value={progressPct} label={`${ch.name} coverage`} className="h-1.5" />
              </div>

              <div className="flex flex-wrap gap-1.5 pt-2 text-xs">
                {ch.unseen > 0 && (
                  <Badge variant="outline" className="text-xs font-normal">
                    {ch.unseen} unseen
                  </Badge>
                )}
                {ch.wrong_last > 0 && (
                  <Badge variant="outline" className="border-destructive/30 text-xs font-normal text-destructive">
                    {ch.wrong_last} mistakes
                  </Badge>
                )}
                {ch.due > 0 && (
                  <Badge variant="default" className="text-xs font-normal">
                    {ch.due} due for review
                  </Badge>
                )}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between border-t pt-4">
              <Button
                size="sm"
                variant="outline"
                className="w-full gap-1.5 text-xs font-semibold"
                disabled={isStarting || ch.available === 0}
                onClick={() => onQuickPractice?.(ch.chapter_id)}
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Quick 10 MCQs
              </Button>
            </div>
          </Card>
        )
      })}
    </div>
  )
}

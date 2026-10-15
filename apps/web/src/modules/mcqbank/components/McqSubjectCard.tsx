import { Badge, Card, ChevronRight } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { SubjectCard } from '../lib/types'

interface McqSubjectCardProps {
  subject: SubjectCard
  className?: string
}

export function McqSubjectCard({ subject, className }: McqSubjectCardProps) {
  return (
    <Card
      className={`group relative overflow-hidden p-5 transition-all hover:border-primary/40 hover:shadow-md ${className ?? ''}`}
    >
      <Link to="/app/mcq/subjects/$subject" params={{ subject: subject.code }} className="block space-y-3">
        <div className="flex items-center justify-between">
          <Badge variant="outline" className="font-mono text-xs uppercase">
            {subject.paper_number ? `Paper ${subject.paper_number}` : subject.code}
          </Badge>
          <span className="text-xs font-medium text-muted-foreground">{subject.total_mcqs} MCQs</span>
        </div>

        <div>
          <h3 className="text-base font-semibold text-foreground transition-colors group-hover:text-primary">
            {subject.name}
          </h3>
        </div>

        <div className="flex items-center justify-between border-t pt-2 text-xs font-medium text-primary">
          <span>Explore Chapters</span>
          <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </div>
      </Link>
    </Card>
  )
}

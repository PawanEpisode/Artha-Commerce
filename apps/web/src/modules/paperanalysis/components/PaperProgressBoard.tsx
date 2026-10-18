import { Badge, Button } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

export interface PaperSummaryItem {
  id: string
  title: string
  subject_key: string
  term_code: string
  paper_kind: string
  total_marks: string
  confirmed_marks: string
  status: 'draft' | 'in_review' | 'published' | 'retracted'
  question_count: number
  progress_pct: number
}

export interface PaperProgressBoardProps {
  papers: PaperSummaryItem[]
  onPublish?: (paperId: string) => Promise<void>
  onUnpublish?: (paperId: string) => Promise<void>
}

export function PaperProgressBoard({ papers, onPublish, onUnpublish }: PaperProgressBoardProps) {
  if (!papers || papers.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No past papers found matching the filter.
      </div>
    )
  }

  const statusBadge = {
    draft: { label: 'Draft', variant: 'outline' as const },
    in_review: { label: 'In Review', variant: 'accent' as const },
    published: { label: 'Published', variant: 'default' as const },
    retracted: { label: 'Retracted', variant: 'outline' as const },
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border bg-muted/40 font-mono text-[10px] tracking-wider text-muted-foreground uppercase">
            <tr>
              <th className="p-3">Paper</th>
              <th className="p-3">Kind</th>
              <th className="p-3">Sitting</th>
              <th className="p-3">Confirmed / Total</th>
              <th className="p-3">Status</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {papers.map((p) => {
              const meta = statusBadge[p.status] || statusBadge.draft
              const isReadyToPublish = parseFloat(p.confirmed_marks) >= parseFloat(p.total_marks) * 0.95

              return (
                <tr key={p.id} className="transition-colors hover:bg-muted/30">
                  <td className="p-3 font-medium text-foreground">
                    <Link
                      to="/app/admin/analysis/papers/$paperId"
                      params={{ paperId: p.id }}
                      className="transition-colors hover:text-primary hover:underline"
                    >
                      {p.title}
                    </Link>
                  </td>
                  <td className="p-3 font-mono text-[11px] text-muted-foreground uppercase">{p.paper_kind}</td>
                  <td className="p-3 font-mono">{p.term_code}</td>
                  <td className="p-3 font-mono">
                    <span className="font-semibold text-foreground">{p.confirmed_marks}</span>
                    <span className="text-muted-foreground"> / {p.total_marks}m</span>
                  </td>
                  <td className="p-3">
                    <Badge variant={meta.variant}>{meta.label}</Badge>
                  </td>
                  <td className="space-x-2 p-3 text-right">
                    <Button variant="ghost" size="sm" asChild>
                      <Link to="/app/admin/analysis/papers/$paperId" params={{ paperId: p.id }}>
                        Workbench
                      </Link>
                    </Button>
                    {p.status !== 'published' && onPublish && (
                      <Button size="sm" disabled={!isReadyToPublish} onClick={() => onPublish(p.id)}>
                        Publish
                      </Button>
                    )}
                    {p.status === 'published' && onUnpublish && (
                      <Button size="sm" variant="outline" onClick={() => onUnpublish(p.id)}>
                        Unpublish
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

import {
  ArchiveRestore,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  FileText,
  Input,
  Notebook,
  Sparkles,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import { useVaultEnrollments } from '../hooks/useProgression'

export function VaultContainer() {
  const { data, isLoading } = useVaultEnrollments()
  const [searchQuery, setSearchQuery] = useState('')

  const filteredEnrollments = useMemo(() => {
    const enrollments = data?.enrollments || []
    if (!searchQuery.trim()) return enrollments
    const query = searchQuery.toLowerCase()
    return enrollments.filter((enr) => {
      const matchLevel = `${enr.course_code} ${enr.level_name} ${enr.term_name}`.toLowerCase().includes(query)
      const matchSubject = enr.subjects.some((s) => s.name.toLowerCase().includes(query))
      return matchLevel || matchSubject
    })
  }, [data?.enrollments, searchQuery])

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground md:text-3xl">
              Past Level Vault
            </h1>
            <Badge variant="outline" className="gap-1 text-xs font-semibold">
              <ArchiveRestore className="size-3.5 text-primary" />
              Preserved
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Read-only archive of notes, annotations, and study materials from your cleared levels.
          </p>
        </div>
        <div className="w-full md:w-72">
          <Input
            placeholder="Search past subjects or notes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9"
          />
        </div>
      </div>

      {/* Informative Banner */}
      <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
        <p>
          <strong className="text-foreground">Cross-Level Reference:</strong> All your handwritten notes, PDF
          highlights, and summaries from earlier levels (e.g. Intermediate Tax, Corporate Law) remain permanently
          accessible here while you prepare for Final.
        </p>
      </div>

      {/* Vault List */}
      {filteredEnrollments.length > 0 ? (
        <div className="space-y-6">
          {filteredEnrollments.map((enr) => (
            <Card key={enr.enrollment_id} className="overflow-hidden">
              <CardHeader className="border-b bg-muted/20 pb-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="default" className="text-xs font-bold uppercase">
                        {enr.course_code}
                      </Badge>
                      <CardTitle className="text-lg">{enr.level_name}</CardTitle>
                    </div>
                    <CardDescription className="mt-1 text-xs">
                      Scheme: {enr.scheme_name} {enr.term_name ? `• Exam Term: ${enr.term_name}` : ''}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Notebook className="size-4 text-primary" />
                      <span>{enr.notes_count} Notes</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <FileText className="size-4 text-primary" />
                      <span>{enr.docs_count} Documents</span>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-4 sm:p-6">
                <h4 className="mb-3 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Preserved Subjects & Papers
                </h4>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {enr.subjects.map((sub) => (
                    <div
                      key={sub.key}
                      className="flex items-center justify-between rounded-lg border bg-card p-3 transition-colors hover:border-primary/40"
                    >
                      <div className="min-w-0 flex-1 pr-2">
                        <p className="truncate text-sm font-medium text-foreground">{sub.name}</p>
                        {sub.paper_number && (
                          <p className="text-[11px] text-muted-foreground">Paper {sub.paper_number}</p>
                        )}
                      </div>
                      <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
                        <Link to="/app/notes/search" search={{ q: sub.name }}>
                          Search Notes
                        </Link>
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<ArchiveRestore />}
          title={searchQuery ? 'No matching subjects found' : 'Your Vault is empty'}
          description={
            searchQuery
              ? 'Try searching with a different term.'
              : 'When you graduate or complete an exam level transition, all notes, bookmarks, and drawings from that level are preserved here.'
          }
          action={
            !searchQuery && (
              <Button asChild size="sm">
                <Link to="/app/transition">Update Level Progress</Link>
              </Button>
            )
          }
        />
      )}
    </div>
  )
}

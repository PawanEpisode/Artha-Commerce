import {
  Badge,
  Briefcase,
  Button,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  DataTable,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  GraduationCap,
  Sparkles,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Undo2,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { useProgressionStatus, useRollbackMutation, useTransitionHistory } from '../hooks/useProgression'

export function ProgressionSettingsContainer() {
  const { data: statusData, isLoading } = useProgressionStatus()
  const { data: historyData } = useTransitionHistory()
  const rollbackMutation = useRollbackMutation()

  const [rollbackTransitionId, setRollbackTransitionId] = useState<string | null>(null)

  const activeEnr = statusData?.active_enrollment
  const exemptions = statusData?.exemptions || []
  const articleship = statusData?.articleship
  const history = historyData?.history || []

  const handleConfirmRollback = async () => {
    if (!rollbackTransitionId) return
    try {
      await rollbackMutation.mutateAsync(rollbackTransitionId)
      setRollbackTransitionId(null)
    } catch {
      // Handled by react-query error
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">Progression & Exemptions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your academic level, paper exemptions, and transition history.
          </p>
        </div>
        <Button asChild className="gap-2 shadow-sm">
          <Link to="/app/transition">
            <Sparkles className="size-4" />
            Update Results / Transition
          </Link>
        </Button>
      </div>

      {/* Active Level Overview Card */}
      {activeEnr && (
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
                  <GraduationCap className="size-5" />
                </div>
                <div>
                  <CardTitle className="text-lg">
                    {activeEnr.course_name} • {activeEnr.level_name}
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Scheme: {activeEnr.scheme_name} {activeEnr.term_name ? `• Target Term: ${activeEnr.term_name}` : ''}
                  </CardDescription>
                </div>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                {activeEnr.daily_minutes ? `${(activeEnr.daily_minutes / 60).toFixed(1)} hrs/day` : 'Flexible'}
              </Badge>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Active Paper Exemptions */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">Official Paper Exemptions (60+ Marks)</h2>
            <p className="text-xs text-muted-foreground">
              Papers where you earned an Institute exemption, carried forward across attempts.
            </p>
          </div>
          <Badge variant="outline" className="text-xs font-semibold">
            {exemptions.length} {exemptions.length === 1 ? 'Exemption' : 'Exemptions'}
          </Badge>
        </div>

        {exemptions.length > 0 ? (
          <div className="overflow-hidden rounded-xl border bg-card">
            <DataTable>
              <TableHeader>
                <TableRow>
                  <TableHead>Paper / Subject</TableHead>
                  <TableHead className="text-center">Marks Scored</TableHead>
                  <TableHead>Granted Term</TableHead>
                  <TableHead>Validity</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {exemptions.map((ex) => (
                  <TableRow key={ex.id}>
                    <TableCell className="font-medium text-foreground">{ex.subject_name}</TableCell>
                    <TableCell className="text-center font-bold text-primary">{ex.marks_obtained}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{ex.granted_term_code}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {ex.is_permanent ? (
                        <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400">
                          Permanent (New Scheme)
                        </Badge>
                      ) : (
                        ex.valid_until_term_code || '3 Terms'
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="default" className="border-success/30 bg-success/20 text-[11px] text-success">
                        Active
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </DataTable>
          </div>
        ) : (
          <Card className="p-6 text-center text-sm text-muted-foreground">
            No paper exemptions recorded yet. When you score ≥ 60 marks in a paper during result transition, it will
            appear here automatically.
          </Card>
        )}
      </div>

      {/* Articleship Lifestyle Summary */}
      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
              <Briefcase className="size-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">
                Practical Training (Articleship): {articleship?.is_active ? 'Active' : 'Full-Time Student'}
              </h3>
              <p className="text-xs text-muted-foreground">
                {articleship?.is_active
                  ? `Firm: ${articleship.firm_name || 'Configured'} • Weekday: ${(articleship.weekday_minutes / 60).toFixed(1)}h • Weekend: ${(articleship.weekend_minutes / 60).toFixed(1)}h`
                  : 'Configure weekday and weekend study split when you start articleship.'}
              </p>
            </div>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/app/settings/articleship">Articleship Planner</Link>
          </Button>
        </div>
      </Card>

      {/* Transition History Ledger */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">Transition History</h2>
          <p className="text-xs text-muted-foreground">
            Audit ledger of level graduations and group updates. Transitions can be undone within 48 hours.
          </p>
        </div>

        {history.length > 0 ? (
          <div className="space-y-3">
            {history.map((item) => (
              <Card key={item.id} className="p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs font-semibold capitalize">
                        {item.transition_type.replace(/_/g, ' ')}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {item.from_level && item.to_level
                        ? `${item.from_level.level_name} → ${item.to_level.level_name}`
                        : 'Syllabus recalibrated'}
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <Badge variant={item.status === 'applied' ? 'default' : 'outline'} className="text-xs capitalize">
                      {item.status}
                    </Badge>
                    {item.can_rollback && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setRollbackTransitionId(item.id)}
                        className="gap-1.5 text-xs text-destructive hover:bg-destructive/10"
                      >
                        <Undo2 className="size-3.5" />
                        Undo (48h)
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="p-6 text-center text-sm text-muted-foreground">No previous transitions recorded.</Card>
        )}
      </div>

      {/* Rollback Confirmation Modal */}
      {rollbackTransitionId && (
        <Dialog open onOpenChange={(open) => !open && setRollbackTransitionId(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Undo Level Transition?</DialogTitle>
              <DialogDescription>
                This will re-activate your previous level syllabus, archive the new level, and restore your prior daily
                targets. This action is safe and does not delete your notes or documents.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRollbackTransitionId(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => void handleConfirmRollback()}
                disabled={rollbackMutation.isPending}
              >
                {rollbackMutation.isPending ? 'Reverting...' : 'Confirm Rollback'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

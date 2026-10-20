interface Props {
  summaryOld?: string | null
  summaryNew?: string | null
  className?: string
}

export function DiffPair({ summaryOld, summaryNew, className }: Props) {
  if (!summaryOld && !summaryNew) return null

  return (
    <div className={`grid grid-cols-1 gap-3 md:grid-cols-2 ${className ?? ''}`}>
      {/* Old / Pre-amendment text */}
      <div className="rounded-md border border-destructive/20 bg-destructive/5 p-3 text-xs leading-relaxed">
        <div className="mb-1 flex items-center justify-between font-semibold text-destructive/80">
          <span>Prior Position</span>
          <span className="text-[10px] tracking-wider text-muted-foreground uppercase">Pre-amendment</span>
        </div>
        <div className="whitespace-pre-wrap text-foreground/90">
          {summaryOld || <span className="text-muted-foreground italic">No prior statutory text recorded.</span>}
        </div>
      </div>

      {/* New / Post-amendment text */}
      <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs leading-relaxed">
        <div className="mb-1 flex items-center justify-between font-semibold text-emerald-600 dark:text-emerald-400">
          <span>New Position</span>
          <span className="text-[10px] tracking-wider text-muted-foreground uppercase">Amended</span>
        </div>
        <div className="whitespace-pre-wrap text-foreground/90">
          {summaryNew || <span className="text-muted-foreground italic">Omitted / deleted without replacement.</span>}
        </div>
      </div>
    </div>
  )
}

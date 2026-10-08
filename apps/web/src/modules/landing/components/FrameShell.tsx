import { Card, cn } from '@artha/design-system'
import type { ReactNode } from 'react'

export function FrameShell({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn('w-full p-5 shadow-lift sm:p-6', className)}>
      <p className="mb-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
      {children}
    </Card>
  )
}

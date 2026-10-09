import { Bell, Clock, Layers, ListChecks, type LucideIcon, Notebook, Settings, Timer } from '@artha/design-system'

import type { WorkspaceLink } from './workspace-nav'

const ICONS: Record<WorkspaceLink['to'], LucideIcon> = {
  '/app/focus': Timer,
  '/app/tracker': Clock,
  '/app/syllabus': ListChecks,
  '/app/notes': Notebook,
  '/app/recall': Layers,
  '/app/settings/focus': Timer,
  '/app/settings/tracker': Clock,
  '/app/settings/coverage': ListChecks,
  '/app/settings/notes': Notebook,
  '/app/settings/notifications': Bell,
  '/app/account': Settings,
}

export const workspaceIcon = (to: WorkspaceLink['to']): LucideIcon => ICONS[to]

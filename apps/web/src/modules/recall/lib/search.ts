import { z } from 'zod'

import { QUEUE_SOURCES } from './api'

/** URL of the review screen. Anything invalid falls back quietly, so a hand-edited link never breaks the page. */
export const reviewSearchSchema = z.object({
  source: z.enum(QUEUE_SOURCES).default('today').catch('today'),
  chapter: z.string().uuid().optional().catch(undefined),
  deck: z.string().uuid().optional().catch(undefined),
  kind: z.string().max(24).optional().catch(undefined),
  tier: z.enum(['bullet', 'important', 'mandatory']).optional().catch(undefined),
  n: z.coerce.number().int().min(1).max(50).optional().catch(undefined),
  /** The session in progress, so a reload carries on the same one. */
  s: z.string().uuid().optional().catch(undefined),
  /** Start with cards due later ("Review ahead 10 cards"). */
  ahead: z.boolean().optional().catch(undefined),
})
export type ReviewSearch = z.infer<typeof reviewSearchSchema>

export const statsSearchSchema = z.object({
  range: z.enum(['7d', '30d', '90d']).default('30d').catch('30d'),
})
export type StatsSearch = z.infer<typeof statsSearchSchema>

/** URL of the quick revision screen: the daily minutes the student can give. Anything invalid means "your usual". */
export const QUICK_MINUTE_CHOICES = [10, 20, 30, 45, 60] as const
export const quickSearchSchema = z.object({
  minutes: z.coerce.number().int().min(5).max(240).optional().catch(undefined),
})
export type QuickSearch = z.infer<typeof quickSearchSchema>

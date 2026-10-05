/** Shapes of `GET /me/` and the onboarding endpoints, validated at the edge (the gate depends on them). */
import { z } from 'zod'

export const avatarSchema = z.object({
  kind: z.enum(['initials', 'preset', 'upload']),
  preset_key: z.string().nullable(),
  version: z.number().int(),
  urls: z.object({ small: z.string(), large: z.string() }).nullable(),
})

export const onboardingStatusSchema = z.enum(['not_started', 'in_progress', 'completed'])

export const onboardingSchema = z.object({
  status: onboardingStatusSchema,
  /** `full` for a new student, `update` for one who finished an earlier version. */
  mode: z.enum(['full', 'update']),
  required_version: z.number().int(),
  completed_version: z.number().int(),
  next_step: z.string().nullable(),
  missing: z.array(z.string()),
})

const named = z.object({ code: z.string(), name: z.string() })

export const courseSummarySchema = z.object({
  course: named,
  level: named,
  term: named.nullable(),
  exam_date: z.string().nullable(),
  days_remaining: z.number().nullable(),
  daily_minutes: z.number().nullable(),
})

export const bootstrapSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string(),
  first_name: z.string(),
  name_suggestion: z.string(),
  avatar: avatarSchema,
  onboarding: onboardingSchema,
  course: courseSummarySchema.nullable(),
  last_visit: z.object({ path: z.string(), search: z.string(), at: z.string().nullable() }).nullable(),
  created_at: z.string().nullable(),
})

export type Avatar = z.infer<typeof avatarSchema>
export type OnboardingSummary = z.infer<typeof onboardingSchema>
export type OnboardingStatus = z.infer<typeof onboardingStatusSchema>
export type CourseSummary = z.infer<typeof courseSummarySchema>
export type Bootstrap = z.infer<typeof bootstrapSchema>

export const stepStateSchema = z.object({
  key: z.string(),
  state: z.enum(['todo', 'done', 'skipped', 'unavailable']),
  mandatory: z.boolean(),
  available: z.boolean(),
})

/** `GET /me/onboarding/` and every step write: the summary plus the step list. */
export const onboardingStateSchema = onboardingSchema.extend({ steps: z.array(stepStateSchema) })
export type OnboardingState = z.infer<typeof onboardingStateSchema>

export const completionSchema = z.object({ state: onboardingStateSchema, destination: z.string() })
export type Completion = z.infer<typeof completionSchema>

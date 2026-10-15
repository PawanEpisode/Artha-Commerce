import { z } from 'zod'

/** `/app/today` search: `paper` filters to one paper, `task` highlights a task, `add` opens the add sheet (W5), `from` says where we came from. */
export const todaySearchSchema = z.object({
  paper: z.string().max(80).optional().catch(undefined),
  task: z.string().uuid().optional().catch(undefined),
  add: z.literal(true).optional().catch(undefined),
  from: z.enum(['workspace', 'notification', 'email']).optional().catch(undefined),
})
export type TodaySearch = z.infer<typeof todaySearchSchema>

import { z } from 'zod'

/** `?chapter=` opens the request form on that chapter; `?batch=` shows one batch of suggestions. */
export const suggestionsSearchSchema = z.object({
  chapter: z.string().optional().catch(undefined),
  batch: z.string().optional().catch(undefined),
})
export type SuggestionsSearch = z.infer<typeof suggestionsSearchSchema>

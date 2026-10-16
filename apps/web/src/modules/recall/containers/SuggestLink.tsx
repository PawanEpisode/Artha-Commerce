import { ButtonLink, Sparkles } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useRecallAiEnabled } from '../hooks/useSuggestions'

/** The way into AI suggestions, shown only while the `recall_ai` flag is on. */
export function SuggestLink({ chapter }: { chapter?: string }) {
  const enabled = useRecallAiEnabled()
  if (!enabled) return null
  return (
    <ButtonLink variant="outline" size="sm" asChild>
      <Link to="/app/recall/suggestions" search={{ chapter }}>
        <Sparkles aria-hidden /> Suggest with AI
      </Link>
    </ButtonLink>
  )
}

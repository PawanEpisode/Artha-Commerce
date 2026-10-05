import { track } from '~/modules/observability'

import { StudyPromptCard } from '../components/StudyPromptCard'
import { useStudyViewer } from '../hooks/useStudyViewer'
import { coursePrompt, coursesHomePrompt, levelPrompt, promptDestination } from '../lib/prompt'

type Surface =
  | { surface: 'home' }
  | { surface: 'course'; course: { slug: string; name: string } }
  | { surface: 'level'; course: { slug: string; name: string }; level: { slug: string; name: string } }

/**
 * Personal next step on the public course pages. Until the session is known, this is the guest prompt, so the
 * action is on the page immediately. A signed-in student then sees their real coverage.
 */
export function CoveragePrompt(props: Surface) {
  const { ready, study } = useStudyViewer()
  const viewer = ready ? study : { signedIn: false, coverageOn: true, snapshot: null }

  const prompt =
    props.surface === 'home'
      ? coursesHomePrompt(viewer)
      : props.surface === 'course'
        ? coursePrompt(viewer, props.course)
        : levelPrompt(viewer, props.course, props.level)
  if (!prompt) return null

  return (
    <StudyPromptCard
      prompt={prompt}
      onOpen={() =>
        track('coverage_prompt_opened', { surface: props.surface, destination: promptDestination(prompt.link) })
      }
    />
  )
}

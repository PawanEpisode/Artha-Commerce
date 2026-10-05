import { Button, Card, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { type StudyLink, type StudyPrompt } from '../lib/prompt'

function PromptLink({ link, onOpen }: { link: StudyLink; onOpen: () => void }) {
  if (link.to === '/app/syllabus') {
    return (
      <Link to="/app/syllabus" onClick={onOpen}>
        {link.label}
      </Link>
    )
  }
  if (link.to === '/app/onboarding') {
    return (
      <Link to="/app/onboarding" search={link.search} onClick={onOpen}>
        {link.label}
      </Link>
    )
  }
  return (
    <Link to="/login" search={link.search} onClick={onOpen}>
      {link.label}
    </Link>
  )
}

function CoverageRing({ value, label }: { value: number; label: string }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(value))
    return () => cancelAnimationFrame(id)
  }, [value])
  return <ProgressRing value={shown} label={label} size={112} strokeWidth={10} />
}

/** The next useful step: a real coverage number, or one tap into setup. */
export function StudyPromptCard({ prompt, onOpen }: { prompt: StudyPrompt; onOpen: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-5 p-6 sm:flex-row sm:items-center">
      {prompt.percent !== undefined ? (
        <CoverageRing value={prompt.percent} label={prompt.progressLabel ?? 'Coverage'} />
      ) : null}
      <div className="min-w-0 flex-1 text-center sm:text-left">
        <p className="text-xl font-bold break-words">{prompt.title}</p>
        <p className="mt-2 text-muted-foreground">{prompt.body}</p>
      </div>
      <Button size="lg" className="w-full sm:w-auto" asChild>
        <PromptLink link={prompt.link} onOpen={onOpen} />
      </Button>
    </Card>
  )
}

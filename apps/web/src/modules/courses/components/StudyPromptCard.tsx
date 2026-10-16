import { Button, Card, ProgressRing } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { type MouseEvent, type ReactNode, useEffect, useState } from 'react'

import { type StudyLink, type StudyPrompt } from '../lib/prompt'

/** Forwards the button styles. A wrapper that drops className renders the action as plain text. */
function PromptLink({
  link,
  onOpen,
  className,
  children,
  onClick,
}: {
  link: StudyLink
  onOpen: () => void
  className?: string
  children?: ReactNode
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void
}) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event)
    onOpen()
  }
  if (link.to === '/app/syllabus') {
    return (
      <Link to="/app/syllabus" className={className} onClick={handleClick}>
        {children}
      </Link>
    )
  }
  if (link.to === '/app/onboarding') {
    return (
      <Link to="/app/onboarding" search={link.search} className={className} onClick={handleClick}>
        {children}
      </Link>
    )
  }
  return (
    <Link to="/login" search={link.search} className={className} onClick={handleClick}>
      {children}
    </Link>
  )
}

function CoverageRing({ value, label }: { value: number; label: string }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(value))
    return () => cancelAnimationFrame(id)
  }, [value])
  return <ProgressRing value={shown} label={label} size={64} strokeWidth={7} />
}

/** The next useful step: a real coverage number, or one tap into setup. */
export function StudyPromptCard({ prompt, onOpen }: { prompt: StudyPrompt; onOpen: () => void }) {
  return (
    <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-4">
      {prompt.percent !== undefined ? (
        <CoverageRing value={prompt.percent} label={prompt.progressLabel ?? 'Coverage'} />
      ) : null}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold break-words">{prompt.title}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{prompt.body}</p>
      </div>
      <Button arrow className="shrink-0" asChild>
        <PromptLink link={prompt.link} onOpen={onOpen}>
          {prompt.link.label}
        </PromptLink>
      </Button>
    </Card>
  )
}

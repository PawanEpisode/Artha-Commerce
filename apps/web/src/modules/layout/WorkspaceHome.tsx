import { Button, cn, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'

import { useWorkspaceNav } from './useWorkspaceNav'
import { workspaceIcon } from './workspace-icons'

/** /app: the signed-in home. Tools and their settings live here so they are reachable without typing a URL. */
export function WorkspaceHome() {
  const { user } = useAuth()
  const { study, settings } = useWorkspaceNav()

  return (
    <Container className="py-10 sm:py-14">
      <header className="max-w-2xl">
        <h1 className="text-3xl font-extrabold">Your workspace</h1>
        <p className="mt-3 break-all text-muted-foreground">
          Signed in as {user?.email}. Open a study tool, or change how it works in settings.
        </p>
      </header>

      {study.length > 0 ? (
        <nav aria-label="Study" className="mt-8">
          <h2 className="sr-only">Study</h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {study.map((item, index) => {
              const Icon = workspaceIcon(item.to)
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className={cn(
                      'flex h-full min-h-11 flex-col gap-2 rounded-xl border bg-card p-5 text-card-foreground shadow-soft outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40',
                      index === 0 ? 'border-primary' : 'border-border',
                    )}
                  >
                    <Icon aria-hidden />
                    {index === 0 ? <span className="text-sm font-semibold text-primary">Start here</span> : null}
                    <span className="text-lg font-semibold">{item.label}</span>
                    {item.description ? (
                      <span className="text-sm text-muted-foreground">{item.description}</span>
                    ) : null}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
      ) : null}

      <nav aria-label="Settings" className="mt-10">
        <h2 className="text-lg font-bold">Settings</h2>
        <ul className="mt-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          {settings.map((item) => {
            const Icon = workspaceIcon(item.to)
            return (
              <li key={item.to} className="sm:w-auto">
                <Button variant="outline" className="w-full sm:w-auto" asChild>
                  <Link to={item.to}>
                    <Icon aria-hidden />
                    {item.label}
                  </Link>
                </Button>
              </li>
            )
          })}
        </ul>
      </nav>
    </Container>
  )
}

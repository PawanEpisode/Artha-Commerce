import { Button, Container, Logo } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'

import { ThemeToggle } from './ThemeToggle'

const nav = [
  { to: '/features', label: 'Features' },
  { to: '/courses', label: 'Courses' },
] as const

export function SiteHeader() {
  const { user, loading } = useAuth()
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
      <Container className="flex h-16 items-center justify-between">
        <Link to="/" aria-label="ArthaCommerce home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {nav.map((item) => (
            <Button key={item.to} variant="ghost" size="sm" asChild>
              <Link to={item.to} activeProps={{ className: 'text-primary' }}>
                {item.label}
              </Link>
            </Button>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {!loading && user ? (
            <Button size="sm" asChild>
              <Link to="/app">Open workspace</Link>
            </Button>
          ) : (
            <Button size="sm" asChild>
              <Link to="/login">Start free</Link>
            </Button>
          )}
        </div>
      </Container>
    </header>
  )
}

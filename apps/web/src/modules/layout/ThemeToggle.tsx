import { Button } from '@artha/design-system'
import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

/** Toggles the `.dark` class. The initial class is set by an inline script in the root document to avoid a flash. */
export function ThemeToggle() {
  const [dark, setDark] = useState(false)

  useEffect(() => setDark(document.documentElement.classList.contains('dark')), [])

  function toggle() {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      /* storage unavailable: theme still applies for this session */
    }
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
}

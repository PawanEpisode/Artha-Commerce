import { Button } from '../components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu'
import { RadioCardItem, RadioGroup } from '../components/ui/radio-group'
import { Check } from '../icons'
import { getThemeOption, THEME_OPTIONS } from './options'
import { isThemePreference } from './theme'
import { useTheme } from './ThemeProvider'

/** Compact header control: icon button that opens a menu of the four themes. */
export function ThemeSwitcher() {
  const { preference, setPreference } = useTheme()
  const current = getThemeOption(preference)
  const CurrentIcon = current.icon
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Theme: ${current.label}. Change theme`}>
          <CurrentIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={preference}
          onValueChange={(v) => {
            if (isThemePreference(v)) setPreference(v)
          }}
        >
          {THEME_OPTIONS.map(({ value, label, description, icon: Icon }) => (
            <DropdownMenuRadioItem key={value} value={value}>
              <Icon />
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{label}</span>
                <span className="block text-xs text-muted-foreground">{description}</span>
              </span>
              {preference === value && <Check aria-hidden className="text-primary" />}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Full-size picker for settings pages (Appearance). Same options and state as ThemeSwitcher. */
export function ThemeRadioGroup({ className }: { className?: string }) {
  const { preference, setPreference } = useTheme()
  return (
    <RadioGroup
      aria-label="Theme"
      value={preference}
      onValueChange={(v) => {
        if (isThemePreference(v)) setPreference(v)
      }}
      className={className}
    >
      {THEME_OPTIONS.map(({ value, label, description, icon: Icon }) => (
        <RadioCardItem key={value} value={value}>
          <span className="flex items-center gap-2 font-semibold">
            <Icon aria-hidden className="size-4 text-primary" />
            {label}
          </span>
          <span className="mt-1 block text-sm text-muted-foreground">{description}</span>
        </RadioCardItem>
      ))}
    </RadioGroup>
  )
}

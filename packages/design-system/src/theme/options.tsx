import { BookOpen, Moon, Sun, SunMoon } from '../icons'
import type { ThemePreference } from './theme'

export interface ThemeOption {
  value: ThemePreference
  label: string
  description: string
  icon: typeof Sun
}

/** Single source for theme labels, copy and icons (used by the header menu and the settings page). */
export const THEME_OPTIONS: readonly ThemeOption[] = [
  { value: 'reading', label: 'Reading', description: 'Warm paper tone, easy on the eyes. Default.', icon: BookOpen },
  { value: 'light', label: 'Light', description: 'Bright and clean.', icon: Sun },
  { value: 'dark', label: 'Dark', description: 'Low light, saves battery on OLED.', icon: Moon },
  {
    value: 'system',
    label: 'System',
    description: 'Light from 6 am to 6 pm, dark from 6 pm to 6 am.',
    icon: SunMoon,
  },
]

export function getThemeOption(value: ThemePreference): ThemeOption {
  return THEME_OPTIONS.find((o) => o.value === value) ?? THEME_OPTIONS[0]
}

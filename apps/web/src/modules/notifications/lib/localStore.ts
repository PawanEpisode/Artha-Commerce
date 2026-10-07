/** Per-device `localStorage` access that tolerates blocked or full storage: nothing here may break a page. */
export const readLocal = (key: string): string | null => {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export const writeLocal = (key: string, value: string | null): void => {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // storage blocked or full: nothing depends on it
  }
}

import { create } from 'zustand'

export type Theme = 'dark' | 'light'

function apply(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try {
    localStorage.setItem('april-theme', theme)
  } catch {
    /* storage unavailable */
  }
}

function initial(): Theme {
  try {
    const saved = localStorage.getItem('april-theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* storage unavailable */
  }
  return 'dark'
}

interface ThemeState {
  theme: Theme
  toggle: () => void
  setTheme: (theme: Theme) => void
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: initial(),
  toggle: () =>
    set((state) => {
      const next: Theme = state.theme === 'dark' ? 'light' : 'dark'
      apply(next)
      return { theme: next }
    }),
  setTheme: (theme) => {
    apply(theme)
    set({ theme })
  },
}))

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import api from '../api/client'

const ThemeContext = createContext(null)

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('theme_preference', theme)
}

export function ThemeProvider({ children }) {
  // Initialize from localStorage (already applied by the inline <script>
  // in index.html, so this just syncs state).
  const [theme, setThemeState] = useState(
    () => localStorage.getItem('theme_preference') || 'dark'
  )

  const setTheme = useCallback(
    (newTheme) => {
      setThemeState(newTheme)
      applyTheme(newTheme)
      // Fire and forget — the UI updates optimistically.
      api
        .put('/auth/me/preferences', { theme_preference: newTheme })
        .catch(() => {
          /* ignore — localStorage is the primary persistence for UX;
             the backend is just for cross-device sync */
        })
    },
    []
  )

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  // When auth loads, sync the server-side preference into local state
  // without triggering a PATCH back. Called from AuthContext after login.
  const syncFromServer = useCallback((serverTheme) => {
    if (serverTheme && serverTheme !== theme) {
      setThemeState(serverTheme)
      applyTheme(serverTheme)
    }
  }, [theme])

  // Make sure the DOM attribute stays in sync if state changes
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme, syncFromServer }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, login as loginApi } from '../api/auth'

const AuthContext = createContext(null)

/** Sync the server-side theme into localStorage + DOM so the user sees
 *  their saved preference immediately after auth.  */
function syncThemeFromUser(userData) {
  if (userData?.theme_preference) {
    const current = localStorage.getItem('theme_preference')
    if (current !== userData.theme_preference) {
      localStorage.setItem('theme_preference', userData.theme_preference)
      document.documentElement.setAttribute('data-theme', userData.theme_preference)
    }
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      getMe()
        .then((data) => {
          setUser(data)
          syncThemeFromUser(data)
        })
        .catch(() => {
          localStorage.removeItem('access_token')
          setUser(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const { access_token } = await loginApi(email, password)
    localStorage.setItem('access_token', access_token)
    const userData = await getMe()
    setUser(userData)
    syncThemeFromUser(userData)
    return userData
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, setCsrf } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    api
      .me()
      .then((me) => {
        setCsrf(me.csrf_token)
        setUser(me)
      })
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const login = useCallback(async (email, password) => {
    const me = await api.login(email, password)
    setCsrf(me.csrf_token)
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setCsrf('')
      setUser(null)
    }
  }, [])

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

export const ROLES = { viewer: 1, operator: 2, admin: 3 }

export function can(user, minimum) {
  if (!user) return false
  return (ROLES[user.role] || 0) >= (ROLES[minimum] || 99)
}

import { useEffect, useState } from 'react'
import { GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from 'firebase/auth'
import { auth } from '../lib/firebase'

const provider = new GoogleAuthProvider()

export function useAuth() {
  const [user, setUser] = useState(undefined)  // undefined = 로딩 중, null = 비로그인

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => setUser(u ?? null))
    return unsub
  }, [])

  const login = () => signInWithPopup(auth, provider).catch(console.error)
  const logout = () => signOut(auth).catch(console.error)

  return { user, loading: user === undefined, login, logout }
}

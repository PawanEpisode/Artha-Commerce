import { useNavigate } from '@tanstack/react-router'
import { type FormEvent, useEffect, useState } from 'react'

import { LoginCard } from '../components/LoginCard'
import { useAuth } from '../hooks/useAuth'

export function LoginContainer() {
  const { user, configured, signInWithEmail, signInWithGoogle } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [message, setMessage] = useState<string>()

  useEffect(() => {
    if (user) void navigate({ to: '/app' })
  }, [user, navigate])

  async function onSubmitEmail(e: FormEvent) {
    e.preventDefault()
    setStatus('sending')
    const { error } = await signInWithEmail(email)
    setStatus(error ? 'error' : 'sent')
    setMessage(error)
  }

  return (
    <LoginCard
      email={email}
      onEmailChange={setEmail}
      onSubmitEmail={onSubmitEmail}
      onGoogle={() => void signInWithGoogle()}
      status={status}
      disabled={!configured}
      message={configured ? message : 'Sign-in is not configured yet. Add the Supabase env vars.'}
    />
  )
}

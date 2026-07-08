'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { Shield, AlertCircle, Eye, EyeOff } from 'lucide-react'

const MAX_ATTEMPTS = 5
const LOCKOUT_SECONDS = 30

// TODO: connect to backend API — replace this stub with a real auth call
async function mockLoginAttempt(key: string, _twoFaCode?: string): Promise<{ success: boolean }> {
  await new Promise((r) => setTimeout(r, 600))
  // Simulates failure for demo purposes
  return { success: false }
}

export default function LoginPage() {
  const [accountKey, setAccountKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [has2FA, setHas2FA] = useState(false)
  const [twoFaCode, setTwoFaCode] = useState('')
  const [error, setError] = useState('')
  const [keyError, setKeyError] = useState('')
  const [twoFaError, setTwoFaError] = useState('')
  const [loading, setLoading] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [locked, setLocked] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (locked && countdown > 0) {
      timerRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current!)
            setLocked(false)
            setAttempts(0)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [locked, countdown])

  // Client-side validation — UX convenience only; real validation happens server-side
  function validateKey(value: string): string {
    if (!value) return 'Account key is required.'
    if (!/^[a-zA-Z0-9]{32}$/.test(value))
      return 'Key must be exactly 32 alphanumeric characters.'
    return ''
  }

  function validateTwoFa(value: string): string {
    if (has2FA && !/^\d{6}$/.test(value)) return '2FA code must be exactly 6 digits.'
    return ''
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const kErr = validateKey(accountKey)
    const tfaErr = validateTwoFa(twoFaCode)
    setKeyError(kErr)
    setTwoFaError(tfaErr)
    if (kErr || tfaErr) return

    setLoading(true)
    setError('')
    try {
      // TODO: connect to backend API
      const result = await mockLoginAttempt(accountKey, has2FA ? twoFaCode : undefined)
      if (result.success) {
        // TODO: redirect to dashboard on success
      } else {
        const newAttempts = attempts + 1
        setAttempts(newAttempts)
        if (newAttempts >= MAX_ATTEMPTS) {
          // NOTE: this is NOT a security control — it is only abuse-friction for legitimate users.
          // Real rate limiting is enforced server-side.
          setLocked(true)
          setCountdown(LOCKOUT_SECONDS)
          setError(`Too many failed attempts. Please wait ${LOCKOUT_SECONDS} seconds before trying again.`)
        } else {
          setError(`Invalid account key${has2FA ? ' or 2FA code' : ''}. ${MAX_ATTEMPTS - newAttempts} attempt${MAX_ATTEMPTS - newAttempts === 1 ? '' : 's'} remaining before temporary lockout.`)
        }
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-16 bg-background">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <Link href="/" className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15 ring-1 ring-primary/30 mb-3">
            <Shield className="h-6 w-6 text-primary" />
          </Link>
          <h1 className="text-xl font-semibold text-foreground">Log in to Stealthy</h1>
          <p className="text-sm text-muted-foreground mt-1">Enter your account key to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* Account key */}
          <div>
            <label htmlFor="account-key" className="block text-sm font-medium text-foreground mb-1.5">
              Account key
            </label>
            <div className="relative">
              <input
                id="account-key"
                type={showKey ? 'text' : 'password'}
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                placeholder="Enter your 32-character account key"
                value={accountKey}
                onChange={(e) => {
                  setAccountKey(e.target.value)
                  if (keyError) setKeyError(validateKey(e.target.value))
                }}
                className="w-full rounded-md border border-input bg-muted px-3 py-2.5 pr-10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                aria-describedby={keyError ? 'key-error' : undefined}
                aria-invalid={!!keyError}
                maxLength={40}
                disabled={locked}
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label={showKey ? 'Hide key' : 'Show key'}
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {keyError && (
              <p id="key-error" role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                {keyError}
              </p>
            )}
          </div>

          {/* 2FA toggle */}
          <div className="flex items-center gap-2">
            <input
              id="has2fa"
              type="checkbox"
              checked={has2FA}
              onChange={(e) => {
                setHas2FA(e.target.checked)
                setTwoFaCode('')
                setTwoFaError('')
              }}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            <label htmlFor="has2fa" className="text-sm text-muted-foreground">
              This account has 2FA enabled
            </label>
          </div>

          {/* 2FA code input */}
          {has2FA && (
            <div>
              <label htmlFor="twofa-code" className="block text-sm font-medium text-foreground mb-1.5">
                2FA verification code
              </label>
              <input
                id="twofa-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="6-digit code"
                value={twoFaCode}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, '').slice(0, 6)
                  setTwoFaCode(v)
                  if (twoFaError) setTwoFaError(validateTwoFa(v))
                }}
                className="w-full rounded-md border border-input bg-muted px-3 py-2.5 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                aria-describedby={twoFaError ? 'twofa-error' : undefined}
                aria-invalid={!!twoFaError}
                disabled={locked}
              />
              {twoFaError && (
                <p id="twofa-error" role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                  {twoFaError}
                </p>
              )}
            </div>
          )}

          {/* Global error */}
          {error && (
            <div role="alert" className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || locked}
            className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? 'Verifying…'
              : locked
              ? `Try again in ${countdown}s`
              : 'Log In'}
          </button>
        </form>

        {/* Lost key warning */}
        <p className="mt-5 text-xs text-muted-foreground text-center leading-relaxed">
          Lost your key? It cannot be recovered. You will need to{' '}
          <Link href="/register" className="text-primary hover:underline">
            create a new account
          </Link>
          .
        </p>

        <p className="mt-4 text-xs text-center text-muted-foreground">
          No account?{' '}
          <Link href="/register" className="text-primary hover:underline">
            Generate an account key
          </Link>
        </p>
      </div>
    </div>
  )
}

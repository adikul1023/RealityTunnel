'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { AlertCircle, KeyRound, ShieldCheck } from 'lucide-react'
import { StealthyLogo } from '@/components/ui/logo'
import { useRouter } from 'next/navigation'
import { api, setSession, getOrCreateDeviceGuid, ApiError } from '@/lib/api'

const MAX_ATTEMPTS = 5
const LOCKOUT_SECONDS = 30

export default function LoginPage() {
  const router = useRouter()
  const [credential, setCredential] = useState('')
  const [has2FA, setHas2FA] = useState(false)
  const [twoFaCode, setTwoFaCode] = useState('')
  const [error, setError] = useState('')
  const [credentialError, setCredentialError] = useState('')
  const [twoFaError, setTwoFaError] = useState('')
  const [loading, setLoading] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [locked, setLocked] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [registeredNotice, setRegisteredNotice] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      if (params.get('registered') === '1') {
        setRegisteredNotice(true)
      }
      const credParam = params.get('credential')
      if (credParam) {
        setCredential(credParam)
      } else {
        const id = params.get('account_id')
        if (id) {
          setCredential(`${id}:`)
        }
      }
    }
  }, [])

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

  function parseCredential(value: string): { accountId: string; masterToken: string } | null {
    const trimmed = value.trim()
    const colonIdx = trimmed.indexOf(':')
    if (colonIdx === -1) return null
    const accountId = trimmed.slice(0, colonIdx).replace(/\s+/g, '').toUpperCase()
    const masterToken = trimmed.slice(colonIdx + 1).replace(/\s+/g, '')
    if (!accountId || !masterToken) return null
    return { accountId, masterToken }
  }

  function validateCredential(value: string): string {
    const trimmed = value.trim()
    if (!trimmed) return 'Stealthy Credential is required.'
    const parsed = parseCredential(trimmed)
    if (!parsed) {
      return 'Invalid credential format. Expected ST-XXXX-XXXX:MasterToken'
    }
    return ''
  }

  function validateTwoFa(value: string): string {
    if (has2FA && !value.trim()) {
      return 'Please enter your 6-digit authenticator code or backup code.'
    }
    return ''
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const credErr = validateCredential(credential)
    const tfaErr = validateTwoFa(twoFaCode)
    setCredentialError(credErr)
    setTwoFaError(tfaErr)
    if (credErr || tfaErr) return

    const parsed = parseCredential(credential)
    if (!parsed) return

    setLoading(true)
    setError('')
    try {
      const res = await api.login({
        account_id: parsed.accountId,
        master_token: parsed.masterToken,
        device_guid: getOrCreateDeviceGuid(),
        two_fa_code: has2FA ? twoFaCode.trim() : undefined,
      })

      setSession({
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
        expiresAt: Date.now() + res.expires_in * 1000,
        accountId: parsed.accountId,
      })
      router.push('/dashboard')
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.code === 'Requires2FA' || (err.status === 401 && err.data?.requires_2fa)) {
          setHas2FA(true)
          setError('Two-factor authentication required. Enter your 6-digit TOTP code or backup code.')
        } else if (err.code === 'ReplayDetected') {
          setError('Security alert: session replay detected. Login denied.')
        } else if (err.code === 'DeviceLimitExceeded') {
          setError('Device limit reached for your subscription plan. Please deactivate another device first.')
        } else if (err.code === 'SubscriptionExpired') {
          setError('Your subscription has expired. Please renew your plan.')
        } else if (err.code === 'MaintenanceMode') {
          setError('Stealthy Billing Server is undergoing scheduled maintenance. Please try again later.')
        } else if (err.code === 'MandatoryUpdate') {
          setError('A mandatory client update is required before signing in.')
        } else if (err.code === 'RateLimited') {
          setError('Too many requests. Please wait a moment before retrying.')
        } else {
          const newAttempts = attempts + 1
          setAttempts(newAttempts)
          if (newAttempts >= MAX_ATTEMPTS) {
            setLocked(true)
            setCountdown(LOCKOUT_SECONDS)
            setError(`Too many failed attempts. Please wait ${LOCKOUT_SECONDS} seconds before trying again.`)
          } else {
            setError(err.message || 'Authentication failed. Please verify your Stealthy Credential.')
          }
        }
      } else {
        setError('Unable to reach Oracle Billing Server. Please verify your connection.')
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
          <Link href="/" className="mb-3">
            <StealthyLogo className="h-12 w-12 text-primary" />
          </Link>
          <h1 className="text-xl font-semibold text-foreground">Log in to Stealthy</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Enter your unified Stealthy Credential
          </p>
        </div>

        {registeredNotice && (
          <div className="mb-5 rounded-xl border border-primary/30 bg-primary/10 p-4 text-sm text-foreground">
            <p className="font-semibold text-primary mb-0.5">Registration complete!</p>
            <p className="text-xs text-muted-foreground">
              Your new credential has been pre-filled below. Click Log In to access your dashboard.
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* Unified Credential field */}
          <div>
            <label htmlFor="credential" className="block text-sm font-medium text-foreground mb-1.5 flex items-center gap-1.5">
              <KeyRound className="h-4 w-4 text-muted-foreground" />
              Stealthy Credential
            </label>
            <input
              id="credential"
              type="password"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="ST-XXXX-XXXX:0c19be2b6f..."
              value={credential}
              onChange={(e) => {
                setCredential(e.target.value)
                if (credentialError) setCredentialError(validateCredential(e.target.value))
              }}
              className="w-full rounded-md border border-input bg-muted px-3.5 py-3 text-sm font-mono text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring"
              aria-describedby={credentialError ? 'credential-error' : undefined}
              aria-invalid={!!credentialError}
              disabled={locked}
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Format: <span className="font-mono">AccountID:MasterToken</span>
            </p>
            {credentialError && (
              <p id="credential-error" role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                {credentialError}
              </p>
            )}
          </div>

          {/* 2FA Verification input */}
          {has2FA && (
            <div className="pt-2">
              <label htmlFor="twofa-code" className="block text-sm font-medium text-foreground mb-1.5 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                2FA Verification Code
              </label>
              <input
                id="twofa-code"
                type="text"
                autoComplete="one-time-code"
                placeholder="6-digit TOTP or backup code"
                value={twoFaCode}
                onChange={(e) => {
                  setTwoFaCode(e.target.value)
                  if (twoFaError) setTwoFaError(validateTwoFa(e.target.value))
                }}
                className="w-full rounded-md border border-input bg-muted px-3.5 py-2.5 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring tracking-widest"
                aria-describedby={twoFaError ? 'twofa-error' : undefined}
                aria-invalid={!!twoFaError}
                disabled={locked}
                autoFocus
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
            <div role="alert" className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || locked}
            className="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? 'Verifying…'
              : locked
              ? `Try again in ${countdown}s`
              : 'Log In'}
          </button>
        </form>

        {/* Lost key warning */}
        <p className="mt-6 text-xs text-muted-foreground text-center leading-relaxed">
          Lost your credential? It cannot be recovered. You will need to{' '}
          <Link href="/register" className="text-primary hover:underline">
            create a new account
          </Link>
          .
        </p>

        <p className="mt-4 text-xs text-center text-muted-foreground">
          No account?{' '}
          <Link href="/register" className="text-primary hover:underline">
            Generate a credential
          </Link>
        </p>
      </div>
    </div>
  )
}

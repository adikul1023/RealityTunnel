'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { AlertCircle, Eye, EyeOff } from 'lucide-react'
import { StealthyLogo } from '@/components/ui/logo'
import { useRouter } from 'next/navigation'
import { api, setSession, getOrCreateDeviceGuid, ApiError } from '@/lib/api'

const MAX_ATTEMPTS = 5
const LOCKOUT_SECONDS = 30

export default function LoginPage() {
  const router = useRouter()
  const [accountId, setAccountId] = useState('')
  const [masterToken, setMasterToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [has2FA, setHas2FA] = useState(false)
  const [twoFaCode, setTwoFaCode] = useState('')
  const [error, setError] = useState('')
  const [accountIdError, setAccountIdError] = useState('')
  const [tokenError, setTokenError] = useState('')
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

  function validateAccountId(value: string): string {
    const trimmed = value.trim()
    if (!trimmed) return 'Account ID is required.'
    if (!/^[A-Za-z0-9-]+$/.test(trimmed)) {
      return 'Account ID contains invalid characters.'
    }
    return ''
  }

  function validateMasterToken(value: string): string {
    if (!value.trim()) return 'Master token is required.'
    return ''
  }

  function validateTwoFa(value: string): string {
    if (has2FA && !/^\d{6}$/.test(value)) return '2FA code must be exactly 6 digits.'
    return ''
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const idErr = validateAccountId(accountId)
    const tokErr = validateMasterToken(masterToken)
    const tfaErr = validateTwoFa(twoFaCode)
    setAccountIdError(idErr)
    setTokenError(tokErr)
    setTwoFaError(tfaErr)
    if (idErr || tokErr || tfaErr) return

    setLoading(true)
    setError('')
    try {
      const res = await api.login({
        account_id: accountId.trim().toUpperCase(),
        master_token: masterToken.trim(),
        device_guid: getOrCreateDeviceGuid(),
        two_fa_code: has2FA ? twoFaCode : undefined,
      })

      setSession({
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
        expiresAt: Date.now() + res.expires_in * 1000,
        accountId: accountId.trim().toUpperCase(),
      })
      router.push('/dashboard')
    } catch (err: any) {
      if (err instanceof ApiError) {
        if (err.code === 'Requires2FA' || (err.status === 401 && err.data?.requires_2fa)) {
          setHas2FA(true)
          setError('Two-factor authentication code required.')
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
            setError(err.message || 'Authentication failed. Please verify your Account ID and Master Token.')
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
          <p className="text-sm text-muted-foreground mt-1">Enter your Account ID and Master Token</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* Account ID */}
          <div>
            <label htmlFor="account-id" className="block text-sm font-medium text-foreground mb-1.5">
              Account ID
            </label>
            <input
              id="account-id"
              type="text"
              autoComplete="username"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="e.g. ST-4921-8812"
              value={accountId}
              onChange={(e) => {
                setAccountId(e.target.value)
                if (accountIdError) setAccountIdError(validateAccountId(e.target.value))
              }}
              className="w-full rounded-md border border-input bg-muted px-3 py-2.5 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              aria-describedby={accountIdError ? 'account-id-error' : undefined}
              aria-invalid={!!accountIdError}
              disabled={locked}
            />
            {accountIdError && (
              <p id="account-id-error" role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                {accountIdError}
              </p>
            )}
          </div>

          {/* Master token */}
          <div>
            <label htmlFor="master-token" className="block text-sm font-medium text-foreground mb-1.5">
              Master Token
            </label>
            <div className="relative">
              <input
                id="master-token"
                type={showToken ? 'text' : 'password'}
                autoComplete="current-password"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                placeholder="Enter your secret master token"
                value={masterToken}
                onChange={(e) => {
                  setMasterToken(e.target.value)
                  if (tokenError) setTokenError(validateMasterToken(e.target.value))
                }}
                className="w-full rounded-md border border-input bg-muted px-3 py-2.5 pr-10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                aria-describedby={tokenError ? 'token-error' : undefined}
                aria-invalid={!!tokenError}
                disabled={locked}
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label={showToken ? 'Hide token' : 'Show token'}
              >
                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {tokenError && (
              <p id="token-error" role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                {tokenError}
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
            Generate a master token
          </Link>
        </p>
      </div>
    </div>
  )
}

'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  Copy,
  Download,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { StealthyLogo } from '@/components/ui/logo'
import { useRouter } from 'next/navigation'
import { api, getOrCreateDeviceGuid, ApiError } from '@/lib/api'
import TwoFactorPanel from '@/components/ui/TwoFactorPanel'

export default function RegisterPage() {
  const router = useRouter()
  const [step, setStep] = useState<'generate' | 'confirm'>('generate')
  const [accountId, setAccountId] = useState('')
  const [masterToken, setMasterToken] = useState('')
  const [keyCopied, setKeyCopied] = useState(false)
  const [keySaved, setKeySaved] = useState(false)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState('')
  const [twoFaExpanded, setTwoFaExpanded] = useState(false)

  const combinedCredential =
    accountId && masterToken ? `${accountId}:${masterToken}` : ''

  async function handleGenerate() {
    setLoading(true)
    setApiError('')
    try {
      const res = await api.registerAccount({ plan_id: 'free' })
      setAccountId(res.account_id)
      setMasterToken(res.master_token)
      setKeySaved(false)
      setKeyCopied(false)

      // Automatically authenticate so optional 2FA setup can be performed immediately
      try {
        const deviceGuid = getOrCreateDeviceGuid()
        await api.login({
          account_id: res.account_id,
          master_token: res.master_token,
          device_guid: deviceGuid,
        })
      } catch {
        // Continue even if immediate auto-login fails
      }

      setStep('confirm')
    } catch (err: any) {
      setApiError(
        err instanceof ApiError
          ? err.message
          : 'Failed to create account. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  function handleCopyCredentials() {
    navigator.clipboard.writeText(combinedCredential)
    setKeyCopied(true)
    setTimeout(() => setKeyCopied(false), 2000)
  }

  function handleDownloadCredentials() {
    const blob = new Blob(
      [
        `Stealthy Credential\n\nCredential:\n${combinedCredential}\n\nGenerated: ${new Date().toISOString()}\n\nKEEP THIS FILE SECURE. Your credential cannot be recovered if lost.`,
      ],
      { type: 'text/plain' }
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stealthy-credential.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleContinue() {
    router.push(
      `/login?registered=1&credential=${encodeURIComponent(combinedCredential)}`
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-16 bg-background">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <Link href="/" className="mb-3">
            <StealthyLogo className="h-12 w-12 text-primary" />
          </Link>
          <h1 className="text-xl font-semibold text-foreground">Create your account</h1>
          <p className="text-sm text-muted-foreground mt-1">
            No email or personal data required
          </p>
        </div>

        {/* Error Display */}
        {apiError && (
          <div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{apiError}</span>
          </div>
        )}

        {/* Step: Generate */}
        {step === 'generate' && (
          <div className="rounded-xl border border-border bg-card p-6 space-y-4 shadow-sm">
            <div>
              <h2 className="font-semibold text-foreground mb-1">
                Step 1 — Generate your credential
              </h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                We use an anonymous unified security credential. No email, password, or personal data required.
              </p>
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Generating Credential...' : 'Generate Credential'}
            </button>
          </div>
        )}

        {/* Step: Confirm / Save credential */}
        {step === 'confirm' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-card p-6 space-y-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-foreground">
                  Your Stealthy Credential
                </h2>
                <button
                  onClick={handleGenerate}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  title="Regenerate credential"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Regenerate
                </button>
              </div>

              {/* Combined Credential display */}
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Stealthy Credential (Account ID : Master Token)
                </span>
                <div className="rounded-lg border border-border bg-muted px-4 py-3">
                  <p className="font-mono text-xs md:text-sm text-foreground font-semibold break-all tracking-wide leading-relaxed">
                    {combinedCredential}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={handleCopyCredentials}
                  className="flex items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2.5 text-xs font-medium text-foreground hover:bg-muted transition-colors"
                >
                  {keyCopied ? (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" /> Copy Credential
                    </>
                  )}
                </button>
                <button
                  onClick={handleDownloadCredentials}
                  className="flex items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2.5 text-xs font-medium text-foreground hover:bg-muted transition-colors"
                >
                  <Download className="h-3.5 w-3.5" /> Save file (.txt)
                </button>
              </div>

              {/* Mandatory confirmation */}
              <label className="flex items-start gap-2.5 cursor-pointer pt-2">
                <input
                  type="checkbox"
                  checked={keySaved}
                  onChange={(e) => setKeySaved(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-input accent-primary flex-shrink-0"
                />
                <span className="text-sm text-foreground">
                  I have safely stored my Stealthy Credential. I understand that if I lose it, my account{' '}
                  <strong className="text-foreground">cannot be recovered</strong>.
                </span>
              </label>
            </div>

            {/* Optional 2FA Accordion */}
            <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <button
                type="button"
                onClick={() => setTwoFaExpanded(!twoFaExpanded)}
                className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      Optional: Set Up Two-Factor Authentication (2FA)
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Secure your account with TOTP codes (Google Authenticator, Authy)
                    </p>
                  </div>
                </div>
                {twoFaExpanded ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </button>
              {twoFaExpanded && (
                <div className="p-4 border-t border-border">
                  <TwoFactorPanel compact />
                </div>
              )}
            </div>

            {/* Continue Button */}
            <button
              onClick={handleContinue}
              disabled={!keySaved || loading}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Continue to Sign In
            </button>

            <p className="text-xs text-center text-muted-foreground">
              Already have a credential?{' '}
              <Link href="/login" className="text-primary hover:underline">
                Log in
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

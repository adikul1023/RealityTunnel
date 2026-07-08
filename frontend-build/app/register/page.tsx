'use client'

import { useState } from 'react'
import Link from 'next/link'
import {
  Shield,
  Copy,
  Download,
  CheckCircle2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from 'lucide-react'

// TODO: connect to backend API — replace with a server-generated key
function generateMockKey(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  return Array.from({ length: 32 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

const MOCK_BACKUP_CODES = [
  'AAAA-1111-XXXX', 'BBBB-2222-YYYY', 'CCCC-3333-ZZZZ', 'DDDD-4444-WWWW',
  'EEEE-5555-VVVV', 'FFFF-6666-UUUU', 'GGGG-7777-TTTT', 'HHHH-8888-SSSS',
]

// TODO: connect to backend API
async function mockRegisterAccount(_key: string, _twoFaCode?: string): Promise<{ success: boolean }> {
  await new Promise((r) => setTimeout(r, 800))
  return { success: true }
}

export default function RegisterPage() {
  const [step, setStep] = useState<'generate' | 'confirm' | '2fa'>('generate')
  const [accountKey, setAccountKey] = useState('')
  const [keyCopied, setKeyCopied] = useState(false)
  const [keySaved, setKeySaved] = useState(false)
  const [show2FA, setShow2FA] = useState(false)
  const [twoFaCode, setTwoFaCode] = useState('')
  const [backupCopied, setBackupCopied] = useState(false)
  const [backupSaved, setBackupSaved] = useState(false)
  const [loading, setLoading] = useState(false)
  const [twoFaError, setTwoFaError] = useState('')

  function handleGenerate() {
    setAccountKey(generateMockKey())
    setKeySaved(false)
    setKeyCopied(false)
    setStep('confirm')
  }

  function handleCopyKey() {
    navigator.clipboard.writeText(accountKey)
    setKeyCopied(true)
    setTimeout(() => setKeyCopied(false), 2000)
  }

  function handleDownloadKey() {
    const blob = new Blob(
      [`Stealthy Account Key\n\n${accountKey}\n\nGenerated: ${new Date().toISOString()}\n\nKEEP THIS FILE SECURE. It cannot be recovered if lost.`],
      { type: 'text/plain' }
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stealthy-account-key.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleCopyBackup() {
    navigator.clipboard.writeText(MOCK_BACKUP_CODES.join('\n'))
    setBackupCopied(true)
    setTimeout(() => setBackupCopied(false), 2000)
  }

  function handleDownloadBackup() {
    const blob = new Blob(
      [`Stealthy 2FA Backup Codes\n\n${MOCK_BACKUP_CODES.join('\n')}\n\nEach code can only be used once.\nGenerated: ${new Date().toISOString()}`],
      { type: 'text/plain' }
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'stealthy-backup-codes.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleContinue() {
    if (show2FA && !/^\d{6}$/.test(twoFaCode)) {
      setTwoFaError('Enter a valid 6-digit verification code.')
      return
    }
    setLoading(true)
    try {
      // TODO: connect to backend API
      await mockRegisterAccount(accountKey, show2FA ? twoFaCode : undefined)
      // TODO: redirect to dashboard on success
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-16 bg-background">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <Link href="/" className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/15 ring-1 ring-primary/30 mb-3">
            <Shield className="h-6 w-6 text-primary" />
          </Link>
          <h1 className="text-xl font-semibold text-foreground">Create your account</h1>
          <p className="text-sm text-muted-foreground mt-1">No email or personal data required</p>
        </div>

        {/* Step: Generate */}
        {step === 'generate' && (
          <div className="rounded-xl border border-border bg-card p-6 space-y-4">
            <div>
              <h2 className="font-semibold text-foreground mb-1">Step 1 — Generate your account key</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Your account key is a randomly generated 32-character string. It is the only
                credential for your account — no email or password. Save it somewhere secure
                before continuing.
              </p>
            </div>
            <button
              onClick={handleGenerate}
              className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Generate Account Key
            </button>
          </div>
        )}

        {/* Step: Confirm / Save key */}
        {step === 'confirm' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-foreground">Your account key</h2>
                <button
                  onClick={handleGenerate}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  title="Regenerate key"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Regenerate
                </button>
              </div>

              {/* Key display */}
              <div className="rounded-lg border border-border bg-muted px-4 py-3">
                <p className="font-mono text-sm text-foreground break-all tracking-widest leading-relaxed">
                  {accountKey}
                </p>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={handleCopyKey}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  {keyCopied ? <CheckCircle2 className="h-4 w-4 text-primary" /> : <Copy className="h-4 w-4" />}
                  {keyCopied ? 'Copied!' : 'Copy'}
                </button>
                <button
                  onClick={handleDownloadKey}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
                >
                  <Download className="h-4 w-4" />
                  Download .txt
                </button>
              </div>

              {/* Mandatory confirmation */}
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={keySaved}
                  onChange={(e) => setKeySaved(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-input accent-primary flex-shrink-0"
                />
                <span className="text-sm text-foreground">
                  I have securely saved my account key. I understand it{' '}
                  <strong className="text-foreground">cannot be recovered</strong> if lost.
                </span>
              </label>
            </div>

            {/* Optional 2FA setup */}
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              <button
                onClick={() => setShow2FA(!show2FA)}
                className="w-full flex items-center justify-between px-6 py-4 text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
              >
                <span>Set up two-factor authentication (optional)</span>
                {show2FA ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
              </button>

              {show2FA && (
                <div className="border-t border-border p-6 space-y-5">
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Scan the QR code below with your authenticator app, or enter the manual code.
                  </p>

                  {/* Mock QR */}
                  <div className="flex items-center justify-center">
                    <div
                      className="h-40 w-40 rounded-lg border border-border bg-muted flex flex-col items-center justify-center gap-2 text-xs text-muted-foreground"
                      role="img"
                      aria-label="Mock QR code placeholder for authenticator app"
                    >
                      <div className="grid grid-cols-5 gap-0.5 opacity-30">
                        {Array.from({ length: 25 }, (_, i) => (
                          <div
                            key={i}
                            className="h-4 w-4 rounded-sm"
                            style={{ background: Math.random() > 0.5 ? 'oklch(0.94 0.005 240)' : 'transparent' }}
                          />
                        ))}
                      </div>
                      <span className="text-[10px]">QR placeholder</span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Manual entry code</p>
                    <div className="rounded-md border border-border bg-muted px-3 py-2 font-mono text-sm text-foreground tracking-wider">
                      MOCK-TOTP-SECRET-KEY-12345
                    </div>
                  </div>

                  <div>
                    <label htmlFor="verify-code" className="block text-sm font-medium text-foreground mb-1.5">
                      Verify — enter the 6-digit code from your app
                    </label>
                    <input
                      id="verify-code"
                      type="text"
                      inputMode="numeric"
                      placeholder="000000"
                      maxLength={6}
                      value={twoFaCode}
                      onChange={(e) => {
                        setTwoFaCode(e.target.value.replace(/\D/g, '').slice(0, 6))
                        setTwoFaError('')
                      }}
                      className="w-full rounded-md border border-input bg-muted px-3 py-2.5 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    {twoFaError && (
                      <p role="alert" className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
                        <AlertCircle className="h-3.5 w-3.5" />
                        {twoFaError}
                      </p>
                    )}
                  </div>

                  {/* Backup codes */}
                  <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 space-y-3">
                    <div>
                      <p className="text-sm font-medium text-foreground mb-0.5">Save your backup codes</p>
                      <p className="text-xs text-muted-foreground">
                        Each code can be used once if you lose access to your authenticator app.
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      {MOCK_BACKUP_CODES.map((code) => (
                        <div key={code} className="rounded border border-border bg-muted px-2 py-1.5 font-mono text-xs text-foreground text-center">
                          {code}
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={handleCopyBackup}
                        className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-muted transition-colors"
                      >
                        {backupCopied ? <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
                        {backupCopied ? 'Copied!' : 'Copy'}
                      </button>
                      <button
                        onClick={handleDownloadBackup}
                        className="flex-1 flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-muted transition-colors"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download .txt
                      </button>
                    </div>
                    <label className="flex items-start gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={backupSaved}
                        onChange={(e) => setBackupSaved(e.target.checked)}
                        className="mt-0.5 h-3.5 w-3.5 rounded border-input accent-primary flex-shrink-0"
                      />
                      <span className="text-xs text-muted-foreground">
                        I have saved these backup codes in a secure location.
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {/* Continue */}
            <button
              onClick={handleContinue}
              disabled={!keySaved || (show2FA && !backupSaved) || loading}
              className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating account…' : 'Continue to Plans'}
            </button>

            <p className="text-xs text-center text-muted-foreground">
              Already have a key?{' '}
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

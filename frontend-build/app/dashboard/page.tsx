'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  Shield,
  Zap,
  ToggleLeft,
  ToggleRight,
  Plus,
  Minus,
  X,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowUpRight,
  Monitor,
  Smartphone,
  Laptop,
  AlertTriangle,
  Download,
  RefreshCw,
} from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'
import { config } from '@/lib/config'
import {
  api,
  isAuthenticated,
  AccountMeResponse,
  DeviceDto,
  BillingPaymentDto,
  ApiError,
  getOrCreateDeviceGuid,
} from '@/lib/api'
import TwoFactorPanel from '@/components/ui/TwoFactorPanel'

function getPlanLimit(plan: string): number {
  const lower = (plan || '').toLowerCase()
  if (lower.includes('standard')) return 2
  if (lower.includes('quarterly')) return 3
  if (lower.includes('yearly')) return 5
  return 1
}

function formatRelative(iso: string): string {
  if (!iso) return 'Unknown'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })
}

type Tab = 'credits' | 'devices' | 'billing' | 'downloads' | 'security'
type Platform = 'windows' | 'android' | 'macos' | string
type TxStatus = 'paid' | 'failed' | 'pending' | string

// ─── Sub-components ───────────────────────────────────────────────────────────
function PlatformIcon({ platform }: { platform: Platform }) {
  const lower = (platform || '').toLowerCase()
  if (lower === 'android') return <Smartphone className="h-5 w-5 text-primary" />
  if (lower === 'macos' || lower === 'ios') return <Laptop className="h-5 w-5 text-primary" />
  return <Monitor className="h-5 w-5 text-primary" />
}

function StatusBadge({ status }: { status: TxStatus }) {
  const s = (status || '').toLowerCase()
  const config = s === 'paid' || s === 'success'
    ? { icon: <CheckCircle2 className="h-3.5 w-3.5" />, label: 'Paid', cls: 'text-primary bg-primary/10 border-primary/20' }
    : s === 'failed'
    ? { icon: <AlertCircle className="h-3.5 w-3.5" />, label: 'Failed', cls: 'text-destructive bg-destructive/10 border-destructive/20' }
    : { icon: <Clock className="h-3.5 w-3.5" />, label: status || 'Pending', cls: 'text-muted-foreground bg-muted border-border' }

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${config.cls}`}>
      {config.icon}
      {config.label}
    </span>
  )
}

function RealDownloadButton({ label, href }: { label: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      <Download className="h-4 w-4" />
      {label}
    </a>
  )
}

// Plan metadata keyed by plan ID (matches planId in plan-cta.tsx)
// QR files named by their exact plan amount — no ambiguity
const PLAN_INFO: Record<string, { label: string; price: string; qr: string }> = {
  basic:     { label: 'Basic Monthly',    price: '₹55/month',    qr: '/qr-55.jpg' },
  standard:  { label: 'Standard Monthly', price: '₹85/month',    qr: '/qr-85.jpg' },
  quarterly: { label: 'Quarterly',        price: '₹145/quarter', qr: '/qr-145.jpg' },
}

// ─── Tab: My Credits ──────────────────────────────────────────────────────────
function CreditsTab({ profile }: { profile: AccountMeResponse | null }) {
  const searchParams = useSearchParams()
  const router = useRouter()

  // Auto-open modal and pre-select plan when coming from the plans page
  const payParam = searchParams.get('pay') || ''
  const initialPlan = PLAN_INFO[payParam] ? payParam : 'basic'

  const [isModalOpen, setIsModalOpen] = useState(!!payParam)
  const [selectedPlan] = useState(initialPlan)
  const [transactionId, setTransactionId] = useState('')
  const [submittingTx, setSubmittingTx] = useState(false)
  const [txMessage, setTxMessage] = useState('')

  const currentPlan = profile?.plan || 'Free'
  const expiresAt = profile?.subscription_expires_at
  const status = profile?.status || 'Active'
  const accountId = profile?.account_id || 'Unknown'

  const planInfo = PLAN_INFO[selectedPlan] || PLAN_INFO.basic

  const handleCloseModal = () => {
    setIsModalOpen(false)
    // Remove the ?pay= param from URL cleanly
    router.replace('/dashboard')
  }

  const handleSubmitTx = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!transactionId.trim()) return

    setSubmittingTx(true)
    setTxMessage('')
    try {
      const res = await fetch('/api/telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transactionId,
          accountId,
          plan: planInfo.label,
          price: planInfo.price,
        }),
      })
      if (!res.ok) throw new Error('Failed to submit')
      setTxMessage(`✅ Transaction submitted! Your ${planInfo.label} plan will be approved within 30 minutes. Approval hours: 6:00 AM – 10:00 PM IST.`)
      setTransactionId('')
    } catch (err) {
      setTxMessage('Failed to submit transaction. Please try again.')
    } finally {
      setSubmittingTx(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Read-Only Billing Mode Notice */}
      <div className="rounded-xl border border-primary/30 bg-primary/10 p-4 text-sm text-foreground flex items-center gap-3">
        <Shield className="h-5 w-5 text-primary flex-shrink-0" />
        <div>
          <strong className="font-semibold">Manual Payment Active:</strong> Pay via UPI QR code, then submit your Transaction ID for approval.
        </div>
      </div>

      {/* Subscription Status */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-foreground">Subscription Status</h2>
          <span className="text-sm font-medium text-primary">{status}</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Your account is currently on the <strong className="text-foreground">{currentPlan} Plan</strong>.
        </p>
      </div>

      {/* Upgrade / Renew */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Current plan</p>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
              <span className="font-semibold text-foreground">{currentPlan} Plan</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Expires on {expiresAt ? formatDate(expiresAt) : 'No expiration date'}
            </p>
          </div>
        </div>
        <div className="mt-5">
          <Link href="/plans" className="inline-block rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted hover:border-primary transition-colors">
            View Plans &amp; Pricing
          </Link>
        </div>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-xl">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold text-foreground">Pay via UPI</h2>
              <button
                onClick={handleCloseModal}
                className="rounded-full p-1 hover:bg-muted text-muted-foreground transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-sm text-muted-foreground mb-1">
              <span className="font-medium text-foreground">{planInfo.label}</span> — {planInfo.price}
            </p>
            <p className="text-xs text-muted-foreground mb-4">
              Scan the QR code with any UPI app (GPay, PhonePe, Paytm, etc.), then paste your Transaction ID below.
            </p>

            {/* QR Code */}
            <div className="flex justify-center mb-5 bg-white p-3 rounded-xl border border-border">
              <img
                key={selectedPlan}
                src={planInfo.qr}
                alt={`${planInfo.label} UPI QR Code`}
                className="w-52 h-52 object-contain"
                onError={(e) => {
                  // Fallback to default if specific QR not found
                  e.currentTarget.onerror = null
                  e.currentTarget.src = '/payment-qr-default.jpg'
                }}
              />
            </div>

            <form onSubmit={handleSubmitTx} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">
                  Transaction ID / UTR Number
                </label>
                <input
                  type="text"
                  required
                  value={transactionId}
                  onChange={(e) => setTransactionId(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                  placeholder="e.g. 123456789012"
                  autoFocus
                />
              </div>

              {txMessage && (
                <p className={`text-sm ${txMessage.includes('submitted') ? 'text-primary' : 'text-destructive'}`}>
                  {txMessage}
                </p>
              )}

              <button
                type="submit"
                disabled={submittingTx || !transactionId.trim()}
                className="w-full rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submittingTx ? 'Submitting…' : 'Submit Transaction'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}


// ─── Tab: My Devices ──────────────────────────────────────────────────────────
function DevicesTab({
  devices,
  profile,
  onRemoveDevice,
}: {
  devices: DeviceDto[]
  profile: AccountMeResponse | null
  onRemoveDevice: (guid: string) => Promise<void>
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [currentDeviceGuid, setCurrentDeviceGuid] = useState('')

  useEffect(() => {
    setCurrentDeviceGuid(getOrCreateDeviceGuid())
  }, [])

  const planName = profile?.plan || 'Free'
  const planLimit = getPlanLimit(planName)

  async function handleRemove(guid: string) {
    setRemoving(guid)
    setError('')
    try {
      await onRemoveDevice(guid)
      setConfirmId(null)
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Failed to remove device.')
    } finally {
      setRemoving(null)
    }
  }

  const deviceToRemove = devices.find((d) => d.device_guid === confirmId)

  return (
    <>
      <div className="space-y-5">
        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Slot usage bar */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">Device slots</span>
            <span className="text-sm font-medium text-foreground">{devices.length} / {planLimit}</span>
          </div>
          <div
            className="h-2 w-full rounded-full bg-muted overflow-hidden"
            role="progressbar"
            aria-valuenow={devices.length}
            aria-valuemax={planLimit}
            aria-label="Device slots used"
          >
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.min((devices.length / planLimit) * 100, 100)}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {Math.max(planLimit - devices.length, 0)} slot{Math.max(planLimit - devices.length, 0) !== 1 ? 's' : ''} remaining on your {planName} Plan
          </p>
        </div>

        {/* Device list */}
        <div className="rounded-xl border border-border bg-card divide-y divide-border overflow-hidden">
          {devices.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <Monitor className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
              <p className="text-sm text-muted-foreground">No devices connected.</p>
            </div>
          ) : (
            devices.map((device) => {
              const isCurrent = device.device_guid === currentDeviceGuid
              return (
                <div key={device.device_guid} className="flex items-center gap-4 px-5 py-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                    <PlatformIcon platform={device.friendly_name || 'windows'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-foreground truncate">
                        {device.friendly_name || (isCurrent ? 'This Device' : device.device_guid)}
                      </p>
                      {isCurrent && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary border border-primary/20">
                          ✓ Current Device
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Last active {formatRelative(device.last_seen_at)}
                    </p>
                  </div>
                  <button
                    onClick={() => setConfirmId(device.device_guid)}
                    className="flex-shrink-0 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-destructive/10 hover:border-destructive/30 hover:text-destructive transition-colors"
                    aria-label={`Remove device`}
                  >
                    {isCurrent ? 'Remove (This Device)' : 'Remove'}
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Confirm removal dialog */}
      {confirmId && deviceToRemove && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
          role="dialog"
          aria-modal="true"
          aria-label="Remove device confirmation"
        >
          <div className="w-full max-w-sm rounded-xl border border-border bg-card shadow-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/15 flex-shrink-0">
                <AlertTriangle className="h-5 w-5 text-destructive" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Remove device?</h3>
                <p className="text-sm text-muted-foreground">This will revoke the session for this device.</p>
              </div>
              <button
                onClick={() => setConfirmId(null)}
                className="ml-auto text-muted-foreground hover:text-foreground"
                aria-label="Cancel"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="rounded-lg border border-border bg-muted px-4 py-3 mb-5 flex items-center gap-3">
              <PlatformIcon platform={deviceToRemove.friendly_name || 'windows'} />
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium text-foreground">
                    {deviceToRemove.friendly_name || deviceToRemove.device_guid}
                  </p>
                  {deviceToRemove.device_guid === currentDeviceGuid && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                      ✓ Current Device
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleRemove(confirmId)}
                disabled={removing === confirmId}
                className="flex-1 rounded-md bg-destructive px-4 py-2.5 text-sm font-semibold text-destructive-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {removing === confirmId ? 'Removing…' : 'Remove Device'}
              </button>
              <button
                onClick={() => setConfirmId(null)}
                className="rounded-md border border-border px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ─── Tab: Billing History ─────────────────────────────────────────────────────
function BillingTab({ transactions }: { transactions: BillingPaymentDto[] }) {
  const list = Array.isArray(transactions)
    ? transactions
    : Array.isArray((transactions as any)?.payments)
    ? (transactions as any).payments
    : []

  const totalPaid = list
    .filter((t: any) => (t?.status || '').toLowerCase() === 'paid')
    .reduce((s: number, t: any) => s + (t?.amount || 0), 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-muted-foreground">Your past transactions and invoices</p>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Total paid</p>
          <p className="text-xl font-bold text-foreground">₹{totalPaid.toLocaleString('en-IN')}</p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Date</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Description</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Amount</th>
                <th className="text-center px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-10 text-center text-muted-foreground">
                    No payment transactions recorded.
                  </td>
                </tr>
              ) : (
                list.map((tx: any, idx: number) => (
                  <tr key={tx.id || (tx as any).payment_id || idx} className="hover:bg-muted/20 transition-colors">
                    <td className="px-6 py-3 text-muted-foreground whitespace-nowrap">{formatDate(tx.created_at)}</td>
                    <td className="px-6 py-3 text-foreground">{tx.description || 'Subscription Payment'}</td>
                    <td className="px-6 py-3 text-right font-medium text-foreground whitespace-nowrap">
                      ₹{(tx.amount || 0).toLocaleString('en-IN')}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <StatusBadge status={tx.status} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="border-t border-border px-5 py-3 bg-muted/20">
          <p className="text-xs text-muted-foreground">All amounts include GST. Invoices available for paid transactions only.</p>
        </div>
      </div>
    </div>
  )
}

// ─── Tab: Downloads ───────────────────────────────────────────────────────────
const DOWNLOAD_PLATFORMS = [
  {
    icon: Monitor,
    name: 'Windows',
    version: 'v1.1.2',
    requirements: 'Windows 10 or later (64-bit)',
    size: '88.8 MB',
    available: true,
    note: 'The application may crash the first time you try to connect. If this happens, open Task Manager, end the "Reality Tunnel" and "Reality Tunnel Helper" tasks, and try again.',
    steps: [
      'Download the installer (setup.exe) and run it.',
      'Accept the license agreement and complete installation.',
      'Launch Stealthy from your Start menu or desktop shortcut.',
      'Enter your 32-character master token when prompted.',
      'Select a server region and click Connect.',
      'Troubleshooting: If it fails to connect or the exit IP shows as "?", open Task Manager, kill "Reality Tunnel" and "Reality Tunnel Helper", then try again.',
    ],
    downloads: [
      { label: 'Windows Installer', sublabel: 'setup.exe (88.8 MB)', href: 'https://github.com/adikul1023/StealthyDownloads/releases/latest/download/setup.exe' },
    ],
  },
  {
    icon: Smartphone,
    name: 'Android',
    version: 'v1.1.2',
    requirements: 'Android 8.0 (Oreo) or later',
    size: '55.6 MB',
    available: true,
    note: 'This is a sideloaded APK — not distributed via the Play Store. You will need to allow installation from unknown sources in your Android settings before installing.',
    steps: [
      'Download the APK file (app-release.apk) to your Android device.',
      'Open Settings → Security (or Privacy) and enable "Install from unknown sources" for your browser or file manager.',
      'Open the downloaded APK and tap Install.',
      'Launch Stealthy from your app drawer.',
      'Enter your 32-character master token when prompted.',
      'Select a server region and tap Connect.',
    ],
    downloads: [
      { label: 'Android APK', sublabel: 'app-release.apk (55.6 MB)', href: 'https://github.com/adikul1023/StealthyDownloads/releases/latest/download/app-release.apk' },
    ],
  },
]

function DownloadsTab() {
  const [release, setRelease] = useState({ version: 'v1.1.2', apkSize: '55.6 MB', exeSize: '88.8 MB' })

  useEffect(() => {
    fetch('https://api.github.com/repos/adikul1023/RealityTunnel/releases/latest')
      .then((res) => res.json())
      .then((data) => {
        if (!data.tag_name) return
        const apk = data.assets?.find((a: any) => a.name === 'app-release.apk')
        const exe = data.assets?.find((a: any) => a.name === 'setup.exe')
        setRelease({
          version: data.tag_name,
          apkSize: apk ? (apk.size / 1048576).toFixed(1) + ' MB' : '55.6 MB',
          exeSize: exe ? (exe.size / 1048576).toFixed(1) + ' MB' : '88.8 MB',
        })
      })
      .catch(() => {})
  }, [])

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Download the Stealthy client for your platform. Your master token is required to connect.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {DOWNLOAD_PLATFORMS.filter((p) => p.available).map((p) => (
          <div key={p.name} className="rounded-xl border border-border bg-card overflow-hidden flex flex-col">
            {/* Header */}
            <div className="border-b border-border p-5 flex items-center gap-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
                <p.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-foreground">{p.name}</h2>
                  <span className="text-xs rounded-full border border-border px-2 py-0.5 text-muted-foreground font-mono">
                    {p.name === 'Android' || p.name === 'Windows' ? release.version : p.version}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{p.requirements} · {p.name === 'Android' ? release.apkSize : p.name === 'Windows' ? release.exeSize : p.size}</p>
              </div>
            </div>

            {/* Download buttons */}
            <div className="p-5 border-b border-border space-y-3">
              {p.downloads.map((dl) => (
                <div key={dl.label} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">{dl.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {dl.sublabel.includes('app-release.apk') ? `app-release.apk (${release.apkSize})` :
                       dl.sublabel.includes('setup.exe') ? `setup.exe (${release.exeSize})` : dl.sublabel}
                    </p>
                  </div>
                  <RealDownloadButton label="Download" href={dl.href} />
                </div>
              ))}
            </div>

            {/* Setup steps */}
            <div className="p-5 flex-1">
              <h3 className="text-sm font-semibold text-foreground mb-3">Setup instructions</h3>
              {p.note && (
                <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-foreground">
                  <strong>Note:</strong> {p.note}
                </div>
              )}
              <ol className="space-y-2.5">
                {p.steps.map((step, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 mt-0.5">
                      <span className="text-[10px] font-bold text-primary">{i + 1}</span>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">{step}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        ))}
      </div>

      {/* Linux — coming soon */}
      <div className="rounded-xl border border-dashed border-border bg-card/50 p-5 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-muted flex-shrink-0">
          <Monitor className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            <h2 className="font-semibold text-foreground">Linux</h2>
            <span className="rounded-full bg-muted border border-border px-2 py-0.5 text-xs text-muted-foreground">
              Coming soon
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            A native Linux client is in development. Check back soon or watch our release notes.
          </p>
        </div>
      </div>
    </div>
  )
}

function SecurityTab() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Security & 2FA</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Add an extra layer of protection to your Stealthy account with Two-Factor Authentication (TOTP).
        </p>
      </div>
      <TwoFactorPanel />
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
const TABS: { id: Tab; label: string }[] = [
  { id: 'credits', label: 'My Credits' },
  { id: 'devices', label: 'My Devices' },
  { id: 'billing', label: 'Billing History' },
  { id: 'downloads', label: 'Downloads' },
  { id: 'security', label: 'Security & 2FA' },
]

export default function DashboardPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<Tab>('credits')
  const [profile, setProfile] = useState<AccountMeResponse | null>(null)
  const [devices, setDevices] = useState<DeviceDto[]>([])
  const [transactions, setTransactions] = useState<BillingPaymentDto[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchDashboardData = useCallback(async () => {
    if (!isAuthenticated()) {
      router.replace('/login')
      return
    }
    setLoading(true)
    setError('')
    try {
      const results = await Promise.allSettled([
        api.getClientMe(),
        api.listDevices(),
        api.getBillingHistory(),
      ])

      const profileData = results[0].status === 'fulfilled' ? results[0].value : null
      const devicesRes = results[1].status === 'fulfilled' ? results[1].value : { devices: [] }
      const rawBilling = results[2].status === 'fulfilled' ? results[2].value : []
      const billingList = Array.isArray(rawBilling)
        ? rawBilling
        : Array.isArray((rawBilling as any)?.payments)
        ? (rawBilling as any).payments
        : []

      if (profileData) setProfile(profileData)
      const activeDevices = Array.isArray(devicesRes?.devices) 
        ? devicesRes.devices.filter((d: any) => d.is_active) 
        : []
      setDevices(activeDevices)
      setTransactions(billingList)

      if (results[0].status === 'rejected') {
        const err = results[0].reason
        if (err instanceof ApiError && err.status === 401) {
          router.replace('/login')
          return
        }
        setError(err?.message || 'Could not load profile from Oracle Billing Server.')
      }
    } finally {
      setLoading(false)
    }
  }, [router])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  async function handleRemoveDevice(guid: string) {
    await api.deactivateDevice(guid)
    setDevices((prev) => prev.filter((d) => d.device_guid !== guid))
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Nav isLoggedIn />

      <main className="flex-1 pt-20 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          {/* Header Info */}
          {profile && (
            <div className="mb-6 rounded-xl border border-border bg-card p-4 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider">Account ID</p>
                <p className="text-sm font-mono font-medium text-foreground">{profile.account_id}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
                  {profile.plan}
                </span>
              </div>
            </div>
          )}

          {/* Error Banner with Retry */}
          {error && (
            <div className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 text-sm text-destructive">
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={fetchDashboardData}
                className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-3 py-1.5 text-xs font-semibold text-destructive-foreground hover:opacity-90 transition-opacity"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </button>
            </div>
          )}

          {/* Tab bar */}
          <div className="flex gap-1 border-b border-border mb-7 overflow-x-auto">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Loading State */}
          {loading && !profile ? (
            <div className="py-20 text-center space-y-3">
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">Loading account data from server…</p>
            </div>
          ) : (
            <>
              {/* Tab content */}
              {activeTab === 'credits' && <CreditsTab profile={profile} />}
              {activeTab === 'devices' && (
                <DevicesTab
                  devices={devices}
                  profile={profile}
                  onRemoveDevice={handleRemoveDevice}
                />
              )}
              {activeTab === 'billing' && <BillingTab transactions={transactions} />}
              {activeTab === 'downloads' && <DownloadsTab />}
              {activeTab === 'security' && <SecurityTab />}
            </>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}

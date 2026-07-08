'use client'

import { useState } from 'react'
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
  Linux,
} from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

// ─── Mock data — TODO: connect to backend API ────────────────────────────────
const MOCK_ACCOUNT = {
  plan: 'Yearly',
  renewalDate: '2027-07-06',
  autoRenew: true,
  usedGB: 23.4,
  totalGB: 40,
  daysLeft: 14,
}

const INITIAL_DEVICES: Device[] = [
  { id: '1', name: 'DESKTOP-WORK', platform: 'windows', lastActive: '2026-07-06T09:15:00Z' },
  { id: '2', name: 'Pixel 8 Pro', platform: 'android', lastActive: '2026-07-05T22:43:00Z' },
  { id: '3', name: 'ThinkPad X1', platform: 'windows', lastActive: '2026-07-04T14:22:00Z' },
]

const PLAN_DEVICE_LIMIT = 5

const TRANSACTIONS = [
  { id: 'TXN-001', date: '2026-07-01', description: 'Yearly Plan — Renewal', amount: 680, status: 'paid', devices: 3 },
  { id: 'TXN-002', date: '2026-06-15', description: '20 GB Data Add-on', amount: 200, status: 'paid', devices: 3 },
  { id: 'TXN-003', date: '2026-05-28', description: '10 GB Data Add-on', amount: 100, status: 'paid', devices: 2 },
  { id: 'TXN-004', date: '2026-05-01', description: 'Yearly Plan — Renewal', amount: 680, status: 'paid', devices: 2 },
  { id: 'TXN-005', date: '2026-04-12', description: '5 GB Data Add-on', amount: 50, status: 'failed', devices: 2 },
  { id: 'TXN-006', date: '2026-03-19', description: '30 GB Data Add-on', amount: 300, status: 'paid', devices: 1 },
  { id: 'TXN-007', date: '2026-03-01', description: 'Monthly Plan — March', amount: 69, status: 'pending', devices: 1 },
  { id: 'TXN-008', date: '2026-02-10', description: 'Yearly Plan — Renewal', amount: 680, status: 'paid', devices: 2 },
]

// For design tweak: Row 8 in the billing table should display "2 devices" in the devices column
// and amount should show as ₹680. The JSON requests specified changes to match this state.

// ─── Types ────────────────────────────────────────────────────────────────────
type Tab = 'credits' | 'devices' | 'billing' | 'downloads'
type PaymentState = 'idle' | 'open' | 'processing' | 'success' | 'failed'
type Platform = 'windows' | 'android' | 'macos'
type TxStatus = 'paid' | 'failed' | 'pending'

interface Device {
  id: string
  name: string
  platform: Platform
  lastActive: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
async function mockPayment(
  _type: 'add-data' | 'upgrade' | 'downgrade',
  _amount: number,
): Promise<{ success: boolean }> {
  await new Promise((r) => setTimeout(r, 1200))
  return { success: Math.random() > 0.3 }
}

function formatRelative(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function PlatformIcon({ platform }: { platform: Platform }) {
  if (platform === 'android') return <Smartphone className="h-5 w-5 text-primary" />
  if (platform === 'macos') return <Laptop className="h-5 w-5 text-primary" />
  return <Monitor className="h-5 w-5 text-primary" />
}

function StatusBadge({ status }: { status: TxStatus }) {
  const config = {
    paid: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, label: 'Paid', cls: 'text-primary bg-primary/10 border-primary/20' },
    failed: { icon: <AlertCircle className="h-3.5 w-3.5" />, label: 'Failed', cls: 'text-destructive bg-destructive/10 border-destructive/20' },
    pending: { icon: <Clock className="h-3.5 w-3.5" />, label: 'Pending', cls: 'text-muted-foreground bg-muted border-border' },
  }[status]

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${config.cls}`}>
      {config.icon}
      {config.label}
    </span>
  )
}

function MockDownloadButton({ label }: { label: string }) {
  return (
    <button
      type="button"
      onClick={() => alert('TODO: connect to backend API — download link not yet available')}
      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      <Download className="h-4 w-4" />
      {label}
    </button>
  )
}

// ─── Tab: My Credits ──────────────────────────────────────────────────────────
function CreditsTab() {
  const [autoRenew, setAutoRenew] = useState(MOCK_ACCOUNT.autoRenew)
  const [gbQty, setGbQty] = useState(5)
  const [paymentState, setPaymentState] = useState<PaymentState>('idle')
  const [paymentType, setPaymentType] = useState<'add-data' | 'upgrade' | 'downgrade'>('add-data')
  const [paymentAmount, setPaymentAmount] = useState(0)

  const usedPct = Math.min((MOCK_ACCOUNT.usedGB / MOCK_ACCOUNT.totalGB) * 100, 100)
  const pricePerGB = 10

  function openPayment(type: 'add-data' | 'upgrade' | 'downgrade', amount: number) {
    setPaymentType(type)
    setPaymentAmount(amount)
    setPaymentState('open')
  }

  async function handlePay() {
    setPaymentState('processing')
    const result = await mockPayment(paymentType, paymentAmount)
    setPaymentState(result.success ? 'success' : 'failed')
  }

  return (
    <>
      <div className="space-y-5">
        {/* Usage meter */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-foreground">Data usage</h2>
            <span className="text-sm text-muted-foreground">{MOCK_ACCOUNT.daysLeft} days remaining until renewal</span>
          </div>
          <div
            className="h-2.5 w-full rounded-full bg-muted overflow-hidden mb-2"
            role="progressbar"
            aria-valuenow={MOCK_ACCOUNT.usedGB}
            aria-valuemax={MOCK_ACCOUNT.totalGB}
            aria-label="Data usage"
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${usedPct}%`,
                background: usedPct > 85 ? 'oklch(0.65 0.22 25)' : 'oklch(0.72 0.16 195)',
              }}
            />
          </div>
          <p className="text-sm text-muted-foreground">
            {MOCK_ACCOUNT.usedGB} GB of {MOCK_ACCOUNT.totalGB} GB used this cycle
          </p>
        </div>

        {/* Plan info */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Current plan</p>
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                <span className="font-semibold text-foreground">{MOCK_ACCOUNT.plan} Plan</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                Renews on{' '}
                {new Date(MOCK_ACCOUNT.renewalDate).toLocaleDateString('en-IN', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}{' '}
                · ₹{MOCK_ACCOUNT.plan === 'Monthly' ? '69/month' : '680/year'} +GST
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Auto-renew</span>
              <button
                onClick={() => setAutoRenew(!autoRenew)}
                className="flex items-center text-primary hover:opacity-80 transition-opacity"
                aria-label={`Auto-renew is ${autoRenew ? 'on' : 'off'}`}
                aria-pressed={autoRenew}
              >
                {autoRenew
                  ? <ToggleRight className="h-7 w-7" />
                  : <ToggleLeft className="h-7 w-7 text-muted-foreground" />}
              </button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {MOCK_ACCOUNT.plan === 'Monthly' ? (
              <button
                onClick={() => openPayment('upgrade', 680)}
                className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Zap className="h-4 w-4" />
                Upgrade to Yearly — ₹680
              </button>
            ) : (
              <button
                onClick={() => openPayment('downgrade', 69)}
                className="flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                Downgrade to Monthly
              </button>
            )}
            <Link
              href="/plans"
              className="flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              View all plans <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Buy more data */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="font-semibold text-foreground mb-1">Buy more data</h2>
          <p className="text-sm text-muted-foreground mb-5">
            Extra data at ₹10/GB, added instantly to this cycle.
          </p>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setGbQty(Math.max(1, gbQty - 1))}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-muted transition-colors"
                aria-label="Decrease"
              >
                <Minus className="h-4 w-4" />
              </button>
              <span className="w-16 text-center font-semibold text-foreground">{gbQty} GB</span>
              <button
                onClick={() => setGbQty(Math.min(100, gbQty + 1))}
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border hover:bg-muted transition-colors"
                aria-label="Increase"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            <span className="text-xl font-bold text-foreground">₹{gbQty * pricePerGB}</span>
            <button
              onClick={() => openPayment('add-data', gbQty * pricePerGB)}
              className="ml-auto flex items-center gap-1.5 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Pay &amp; add data
            </button>
          </div>
        </div>
      </div>

      {/* Payment Modal */}
      {paymentState !== 'idle' && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-sm rounded-xl border border-border bg-card shadow-xl p-6">
            {paymentState === 'open' && (
              <>
                <div className="flex items-center justify-between mb-5">
                  <h3 className="font-semibold text-foreground">Complete Payment</h3>
                  <button onClick={() => setPaymentState('idle')} aria-label="Close">
                    <X className="h-5 w-5 text-muted-foreground hover:text-foreground" />
                  </button>
                </div>
                <div className="rounded-lg border border-border bg-muted p-4 mb-5">
                  <p className="text-xs text-muted-foreground mb-1">
                    {paymentType === 'add-data' ? `${gbQty} GB data top-up` : paymentType === 'upgrade' ? 'Upgrade to Yearly Plan' : 'Downgrade to Monthly Plan'}
                  </p>
                  <p className="text-3xl font-bold text-foreground">₹{paymentAmount}</p>
                  <p className="text-xs text-muted-foreground mt-1">GST included</p>
                </div>
                <div className="rounded-lg border border-dashed border-border bg-muted/40 p-4 mb-5 text-center text-sm text-muted-foreground">
                  {/* TODO: connect to backend API — integrate real payment gateway here */}
                  UPI / Card / Netbanking fields would appear here
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handlePay}
                    className="flex-1 rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    Pay ₹{paymentAmount}
                  </button>
                  <button
                    onClick={() => setPaymentState('idle')}
                    className="rounded-md border border-border px-4 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}

            {paymentState === 'processing' && (
              <div className="flex flex-col items-center py-8 gap-4">
                <div className="h-10 w-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                <p className="text-sm text-muted-foreground">Processing payment…</p>
              </div>
            )}

            {paymentState === 'success' && (
              <div className="flex flex-col items-center py-8 gap-4 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/15">
                  <CheckCircle2 className="h-7 w-7 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground mb-1">Payment successful</h3>
                  <p className="text-sm text-muted-foreground">Your account has been updated.</p>
                </div>
                <button
                  onClick={() => setPaymentState('idle')}
                  className="rounded-md bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  Done
                </button>
              </div>
            )}

            {paymentState === 'failed' && (
              <div className="flex flex-col items-center py-8 gap-4 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/15">
                  <AlertCircle className="h-7 w-7 text-destructive" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground mb-1">Payment failed</h3>
                  <p className="text-sm text-muted-foreground">
                    Something went wrong. Please try again or use a different payment method.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPaymentState('open')}
                    className="rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
                  >
                    Try again
                  </button>
                  <button
                    onClick={() => setPaymentState('idle')}
                    className="rounded-md border border-border px-5 py-2.5 text-sm text-foreground hover:bg-muted transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}

// ─── Tab: My Devices ──────────────────────────────────────────────────────────
function DevicesTab() {
  const [devices, setDevices] = useState<Device[]>(INITIAL_DEVICES)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  async function handleRemove(id: string) {
    setRemoving(id)
    // TODO: connect to backend API — remove device session
    await new Promise((r) => setTimeout(r, 600))
    setDevices((prev) => prev.filter((d) => d.id !== id))
    setConfirmId(null)
    setRemoving(null)
  }

  const deviceToRemove = devices.find((d) => d.id === confirmId)

  return (
    <>
      <div className="space-y-5">
        {/* Slot usage bar */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted-foreground">Device slots</span>
            <span className="text-sm font-medium text-foreground">{devices.length} / {PLAN_DEVICE_LIMIT}</span>
          </div>
          <div
            className="h-2 w-full rounded-full bg-muted overflow-hidden"
            role="progressbar"
            aria-valuenow={devices.length}
            aria-valuemax={PLAN_DEVICE_LIMIT}
            aria-label="Device slots used"
          >
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${(devices.length / PLAN_DEVICE_LIMIT) * 100}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {PLAN_DEVICE_LIMIT - devices.length} slot{PLAN_DEVICE_LIMIT - devices.length !== 1 ? 's' : ''} remaining on your {MOCK_ACCOUNT.plan} Plan
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
            devices.map((device) => (
              <div key={device.id} className="flex items-center gap-4 px-5 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 flex-shrink-0">
                  <PlatformIcon platform={device.platform} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground truncate">{device.name}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {device.platform} · Last active {formatRelative(device.lastActive)}
                  </p>
                </div>
                <button
                  onClick={() => setConfirmId(device.id)}
                  className="flex-shrink-0 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-destructive/10 hover:border-destructive/30 hover:text-destructive transition-colors"
                  aria-label={`Remove ${device.name}`}
                >
                  Remove
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Confirm removal dialog */}
      {confirmId && deviceToRemove && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4"
          role="dialog"
          aria-modal="true"
          aria-label={`Remove ${deviceToRemove.name}`}
        >
          <div className="w-full max-w-sm rounded-xl border border-border bg-card shadow-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/15 flex-shrink-0">
                <AlertTriangle className="h-5 w-5 text-destructive" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Remove device?</h3>
                <p className="text-sm text-muted-foreground">This will end the session for this device.</p>
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
              <PlatformIcon platform={deviceToRemove.platform} />
              <div>
                <p className="text-sm font-medium text-foreground">{deviceToRemove.name}</p>
                <p className="text-xs text-muted-foreground capitalize">{deviceToRemove.platform}</p>
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
function BillingTab() {
  const totalPaid = TRANSACTIONS.filter((t) => t.status === 'paid').reduce((s, t) => s + t.amount, 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-muted-foreground">Your past transactions and invoices</p>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Total paid (all time)</p>
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
                <th className="text-center px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Devices</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Amount</th>
                <th className="text-center px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
                <th className="text-center px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Invoice</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {TRANSACTIONS.map((tx) => (
                <tr key={tx.id} className="hover:bg-muted/20 transition-colors">
                  <td className="px-6 py-3 text-muted-foreground whitespace-nowrap">{formatDate(tx.date)}</td>
                  <td className="px-6 py-3 text-foreground">{tx.description}</td>
                  <td className="px-6 py-3 text-center">
                    <span className="text-sm text-foreground font-medium text-center block">{tx.devices} device{tx.devices !== 1 ? 's' : ''}</span>
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-foreground whitespace-nowrap">
                    ₹{tx.amount.toLocaleString('en-IN')}
                  </td>
                  <td className="px-6 py-3 text-center">
                    <StatusBadge status={tx.status as TxStatus} />
                  </td>
                  <td className="px-6 py-3 text-center">
                    {tx.status === 'paid' ? (
                      <button
                        type="button"
                        onClick={() => alert(`TODO: connect to backend API — download invoice ${tx.id}`)}
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                        aria-label={`Download invoice for ${tx.id}`}
                      >
                        <Download className="h-3 w-3" />
                        Invoice
                      </button>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
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
    version: 'v2.4.1',
    requirements: 'Windows 10 or later (64-bit)',
    size: '~18 MB',
    available: true,
    steps: [
      'Download the installer (.exe) and run it.',
      'Accept the license agreement and complete installation.',
      'Launch NullRoute from your Start menu or desktop shortcut.',
      'Enter your 32-character account key when prompted.',
      'Select a server region and click Connect.',
    ],
    downloads: [
      { label: 'Installer (.exe)', sublabel: '~18 MB' },
      { label: 'Portable (.zip)', sublabel: '~20 MB' },
    ],
  },
  {
    icon: Smartphone,
    name: 'Android',
    version: 'v2.3.8',
    requirements: 'Android 8.0 (Oreo) or later',
    size: '~12 MB',
    available: true,
    steps: [
      'Download the APK file to your Android device.',
      'Enable "Install from unknown sources" in device settings if prompted.',
      'Open the downloaded APK and follow the installation prompts.',
      'Launch NullRoute and enter your 32-character account key.',
      'Grant VPN permissions when the system dialog appears, then tap Connect.',
    ],
    downloads: [
      { label: 'APK (arm64-v8a)', sublabel: '~12 MB' },
      { label: 'APK (armeabi-v7a)', sublabel: '~11 MB' },
    ],
  },
  {
    icon: Monitor,
    name: 'Linux',
    version: null,
    requirements: null,
    size: null,
    available: false,
    steps: [],
    downloads: [],
  },
]

function DownloadsTab() {
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Download the NullRoute client for your platform. Your account key is required to connect.
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
                    {p.version}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{p.requirements} · {p.size}</p>
              </div>
            </div>

            {/* Download buttons */}
            <div className="p-5 border-b border-border space-y-3">
              {p.downloads.map((dl) => (
                <div key={dl.label} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">{dl.label}</p>
                    <p className="text-xs text-muted-foreground">{dl.sublabel}</p>
                  </div>
                  <MockDownloadButton label="Download" />
                </div>
              ))}
            </div>

            {/* Setup steps */}
            <div className="p-5 flex-1">
              <h3 className="text-sm font-semibold text-foreground mb-3">Setup instructions</h3>
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

// ─── Main page ────────────────────────────────────────────────────────────────
const TABS: { id: Tab; label: string }[] = [
  { id: 'credits', label: 'My Credits' },
  { id: 'devices', label: 'My Devices' },
  { id: 'billing', label: 'Billing History' },
  { id: 'downloads', label: 'Downloads' },
]

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<Tab>('credits')

  return (
    <div className="flex min-h-screen flex-col">
      <Nav isLoggedIn />

      <main className="flex-1 pt-20 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
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

          {/* Tab content */}
          {activeTab === 'credits' && <CreditsTab />}
          {activeTab === 'devices' && <DevicesTab />}
          {activeTab === 'billing' && <BillingTab />}
          {activeTab === 'downloads' && <DownloadsTab />}
        </div>
      </main>

      <Footer />
    </div>
  )
}

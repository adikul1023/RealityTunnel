'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { StealthyLogo } from '@/components/ui/logo'
import {
  Users,
  Radio,
  CreditCard,
  Layers,
  Database,
  RefreshCw,
  LogOut,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Search,
  Filter,
  ArrowDownToLine,
  Activity,
  Cpu,
  HardDrive
} from 'lucide-react'

// Mock initial transactions (comprehensive, matching plans)
const MOCK_TRANSACTIONS = [
  { id: 'TXN-101', date: '2026-07-10', accountKey: 'zK8x9p2mQ1wR4v7tN3c6y9s1b5f8g2j1', plan: 'Quarterly', amount: 179, status: 'paid', devices: 1 },
  { id: 'TXN-102', date: '2026-07-10', accountKey: 'aB2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q', plan: 'Standard Monthly', amount: 99, status: 'paid', devices: 2 },
  { id: 'TXN-103', date: '2026-07-09', accountKey: 'yT8u9i0o1p2a3s4d5f6g7h8j9k0l1m2n', plan: 'Basic Monthly', amount: 69, status: 'paid', devices: 1 },
  { id: 'TXN-104', date: '2026-07-09', accountKey: 'wQ2e3r4t5y6u7i8o9p0a1s2d3f4g5h6j', plan: 'Quarterly', amount: 179, status: 'failed', devices: 1 },
  { id: 'TXN-105', date: '2026-07-08', accountKey: 'hJ8k9l0z1x2c3v4b5n6m7q8w9e0r1t2y', plan: 'Standard Monthly', amount: 99, status: 'pending', devices: 2 },
  { id: 'TXN-106', date: '2026-07-08', accountKey: 'uI2o3p4a5s6d7f8g9h0j1k2l3z4x5c6v', plan: 'Basic Monthly', amount: 69, status: 'paid', devices: 1 },
  { id: 'TXN-107', date: '2026-07-07', accountKey: 'rT2y3u4i5o6p7a8s9d0f1g2h3j4k5l6z', plan: 'Basic Monthly', amount: 69, status: 'failed', devices: 1 },
  { id: 'TXN-108', date: '2026-07-07', accountKey: 'mN3b4v5c6x7z8a9s0d1f2g3h4j5k6l7q', plan: 'Quarterly', amount: 179, status: 'paid', devices: 1 },
  { id: 'TXN-109', date: '2026-07-06', accountKey: 'kL4j5h6g7f8d9s0a1q2w3e4r5t6y7u8i', plan: 'Standard Monthly', amount: 99, status: 'paid', devices: 2 },
  { id: 'TXN-110', date: '2026-07-06', accountKey: 'pP9o8i7u6y5t4r3e2w1q0asdfghjklzx', plan: 'Basic Monthly', amount: 69, status: 'paid', devices: 1 },
]

export default function AdminDashboard() {
  const router = useRouter()
  const [authenticated, setAuthenticated] = useState(false)
  const [loadingAuth, setLoadingAuth] = useState(true)

  // System stats states
  const [stats, setStats] = useState({
    subscribers: 1248,
    activeUsers: 482,
    monthlyRevenue: 142850,
    totalDevices: 654,
  })

  // Action logs state
  const [actionLogs, setActionLogs] = useState<string[]>([
    `[${new Date().toLocaleTimeString()}] Operations console initialized.`,
  ])

  // Real-time server graph simulation
  const [cpuUsage, setCpuUsage] = useState<number[]>([25, 30, 45, 35, 40, 50, 48, 55, 60, 50, 45, 40])
  const [networkLoad, setNetworkLoad] = useState<number[]>([150, 160, 180, 175, 190, 210, 205, 230, 250, 240, 220, 200])

  // Transaction table states
  const [transactions, setTransactions] = useState(MOCK_TRANSACTIONS)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [planFilter, setPlanFilter] = useState('all')

  // Auth Guard
  useEffect(() => {
    const isAuth = sessionStorage.getItem('admin_authenticated') === 'true'
    if (!isAuth) {
      window.location.href = '/login'
    } else {
      setAuthenticated(true)
      setLoadingAuth(false)
    }
  }, [])

  // Simulation: live updates to CPU/Network graph
  useEffect(() => {
    if (!authenticated) return

    const interval = setInterval(() => {
      setCpuUsage((prev) => [...prev.slice(1), Math.floor(Math.random() * 40) + 20])
      setNetworkLoad((prev) => [...prev.slice(1), Math.floor(Math.random() * 100) + 150])
      // Randomly change active users count slightly to make it feel alive
      setStats((prev) => ({
        ...prev,
        activeUsers: Math.min(600, Math.max(300, prev.activeUsers + Math.floor(Math.random() * 7) - 3)),
      }))
    }, 3000)

    return () => clearInterval(interval)
  }, [authenticated])

  // Sign out handler
  const handleSignOut = () => {
    sessionStorage.removeItem('admin_authenticated')
    window.location.href = '/login'
  }

  // Trigger maintenance tasks
  const handleAction = (actionName: string) => {
    const time = new Date().toLocaleTimeString()
    let logMsg = ''

    if (actionName === 'backup') {
      logMsg = `[${time}] DB Backup triggered: backup_full_${Date.now()}.tar.gz generated.`
    } else if (actionName === 'secret') {
      logMsg = `[${time}] Ed25519 Token secret keys rotated successfully. Old tokens invalidated.`
    } else if (actionName === 'cache') {
      logMsg = `[${time}] Redis system cache flushed. 1,482 expired keys deleted.`
    }

    setActionLogs((prev) => [logMsg, ...prev].slice(0, 15))
  }

  // Filter transactions
  const filteredTransactions = transactions.filter((t) => {
    const matchesSearch =
      t.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.accountKey.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter
    const matchesPlan = planFilter === 'all' || t.plan === planFilter
    return matchesSearch && matchesStatus && matchesPlan
  })

  if (loadingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Authenticating admin session...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Admin Navbar */}
      <header className="border-b border-border bg-card/50 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <StealthyLogo className="h-7 w-7 text-primary" />
              <span className="font-semibold tracking-tight text-foreground text-lg">
                Stealthy Ops Dashboard
              </span>
              <span className="hidden sm:inline-block rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-xs text-primary font-medium">
                Admin Panel
              </span>
            </div>

            <button
              onClick={handleSignOut}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors font-medium"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 md:p-8 space-y-6 max-w-7xl mx-auto w-full">
        
        {/* Statistics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Card 1: Subscribers */}
          <div className="rounded-xl border border-border bg-card p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Total Subscribers
              </p>
              <h3 className="text-3xl font-bold mt-1 text-foreground">
                {stats.subscribers.toLocaleString()}
              </h3>
              <p className="text-xs text-primary mt-1 flex items-center gap-1">
                <span className="font-semibold">Live billing active</span>
              </p>
            </div>
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <Users className="h-6 w-6" />
            </div>
          </div>

          {/* Card 2: Active Users */}
          <div className="rounded-xl border border-border bg-card p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Active Connections
              </p>
              <h3 className="text-3xl font-bold mt-1 text-foreground">
                {stats.activeUsers.toLocaleString()}
              </h3>
              <p className="text-xs text-green-500 mt-1 flex items-center gap-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
                </span>
                Active tunnels now
              </p>
            </div>
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <Radio className="h-6 w-6" />
            </div>
          </div>

          {/* Card 3: Connected Devices */}
          <div className="rounded-xl border border-border bg-card p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Total Registered Devices
              </p>
              <h3 className="text-3xl font-bold mt-1 text-foreground">
                {stats.totalDevices.toLocaleString()}
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Avg 1.8 devices/account
              </p>
            </div>
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <Layers className="h-6 w-6" />
            </div>
          </div>

          {/* Card 4: Revenue */}
          <div className="rounded-xl border border-border bg-card p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Monthly Est. Revenue
              </p>
              <h3 className="text-3xl font-bold mt-1 text-foreground">
                ₹{stats.monthlyRevenue.toLocaleString()}
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                GST included
              </p>
            </div>
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <CreditCard className="h-6 w-6" />
            </div>
          </div>
        </div>

        {/* Live Metrics & Actions Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Real-time Charts Block */}
          <div className="lg:col-span-2 rounded-xl border border-border bg-card p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-foreground flex items-center gap-1.5">
                <Activity className="h-4.5 w-4.5 text-primary" />
                Live Server Operations
              </h2>
              <span className="text-xs text-muted-foreground">Auto-updates every 3s</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* CPU Chart */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold flex items-center gap-1"><Cpu className="h-3.5 w-3.5 text-primary" />CPU Utilization</span>
                  <span className="text-primary font-bold">{cpuUsage[cpuUsage.length - 1]}%</span>
                </div>
                <div className="h-24 bg-muted/40 rounded-lg flex items-end justify-between px-2 py-1 gap-1 border border-border/30">
                  {cpuUsage.map((val, idx) => (
                    <div
                      key={idx}
                      className="bg-primary/80 hover:bg-primary w-full rounded-t transition-all duration-300"
                      style={{ height: `${val}%` }}
                      title={`CPU: ${val}%`}
                    />
                  ))}
                </div>
              </div>

              {/* Bandwidth Chart */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold flex items-center gap-1"><HardDrive className="h-3.5 w-3.5 text-primary" />Network Output</span>
                  <span className="text-primary font-bold">{networkLoad[networkLoad.length - 1]} Mbps</span>
                </div>
                <div className="h-24 bg-muted/40 rounded-lg flex items-end justify-between px-2 py-1 gap-1 border border-border/30">
                  {networkLoad.map((val, idx) => {
                    const pct = (val / 300) * 100 // Scale to 300 max
                    return (
                      <div
                        key={idx}
                        className="bg-cyan-500/80 hover:bg-cyan-500 w-full rounded-t transition-all duration-300"
                        style={{ height: `${pct}%` }}
                        title={`Traffic: ${val} Mbps`}
                      />
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions Panel */}
          <div className="rounded-xl border border-border bg-card p-6 flex flex-col space-y-4">
            <h2 className="text-base font-bold text-foreground flex items-center gap-1.5">
              <Database className="h-4.5 w-4.5 text-primary" />
              Administrative Actions
            </h2>

            <div className="grid grid-cols-1 gap-2.5">
              <button
                onClick={() => handleAction('secret')}
                className="flex items-center justify-between rounded-lg border border-border bg-background p-2.5 text-sm hover:bg-muted transition-colors font-medium text-left"
              >
                <span>Rotate Secret Keys</span>
                <RefreshCw className="h-4 w-4 text-primary" />
              </button>
              <button
                onClick={() => handleAction('backup')}
                className="flex items-center justify-between rounded-lg border border-border bg-background p-2.5 text-sm hover:bg-muted transition-colors font-medium text-left"
              >
                <span>Trigger DB Backup</span>
                <ArrowDownToLine className="h-4 w-4 text-primary" />
              </button>
              <button
                onClick={() => handleAction('cache')}
                className="flex items-center justify-between rounded-lg border border-border bg-background p-2.5 text-sm hover:bg-muted transition-colors font-medium text-left"
              >
                <span>Flush System Cache</span>
                <RefreshCw className="h-4 w-4 text-primary" />
              </button>
            </div>

            {/* Operations Console Logs */}
            <div className="flex-1 min-h-[90px] bg-background/80 rounded-lg border border-border p-3 font-mono text-[10px] text-muted-foreground overflow-y-auto space-y-1">
              <div className="text-primary border-b border-border/40 pb-1 mb-1 font-bold">Terminal logs:</div>
              {actionLogs.map((log, idx) => (
                <div key={idx} className="leading-relaxed animate-in fade-in duration-300">
                  {log}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* System Component Health */}
        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
          <h2 className="text-base font-bold text-foreground flex items-center gap-1.5">
            <Activity className="h-4.5 w-4.5 text-primary" />
            Infrastructure Status (Health Check)
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* PostgreSQL */}
            <div className="bg-background rounded-lg border border-border p-4 flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-foreground">PostgreSQL Database</h4>
                <p className="text-[10px] text-muted-foreground">Connected · 1.4ms latency</p>
              </div>
            </div>

            {/* Redis */}
            <div className="bg-background rounded-lg border border-border p-4 flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-foreground">Redis Memory Cache</h4>
                <p className="text-[10px] text-muted-foreground">Reachable · 0.4ms latency</p>
              </div>
            </div>

            {/* Marzban */}
            <div className="bg-background rounded-lg border border-border p-4 flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-foreground">Marzban API Gateway</h4>
                <p className="text-[10px] text-muted-foreground">Connected · 48ms latency</p>
              </div>
            </div>

            {/* Razorpay */}
            <div className="bg-background rounded-lg border border-border p-4 flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-foreground">Razorpay API Gateway</h4>
                <p className="text-[10px] text-muted-foreground">Connected · 120ms latency</p>
              </div>
            </div>
          </div>
        </div>

        {/* Transactions Table Section */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="border-b border-border p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <h2 className="text-base font-bold text-foreground flex items-center gap-1.5">
              <CreditCard className="h-4.5 w-4.5 text-primary" />
              Subscribers Transaction History
            </h2>

            {/* Table Filters */}
            <div className="flex flex-wrap gap-2.5 items-center">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search ID or key"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors w-full sm:w-44"
                />
              </div>

              {/* Plan Filter */}
              <div className="relative flex items-center border border-border bg-background rounded-lg px-2">
                <Filter className="h-3 w-3 text-muted-foreground mr-1" />
                <select
                  value={planFilter}
                  onChange={(e) => setPlanFilter(e.target.value)}
                  className="bg-transparent py-1.5 text-xs text-foreground outline-none cursor-pointer"
                >
                  <option value="all">All Plans</option>
                  <option value="Basic Monthly">Basic Monthly</option>
                  <option value="Standard Monthly">Standard Monthly</option>
                  <option value="Quarterly">Quarterly</option>
                </select>
              </div>

              {/* Status Filter */}
              <div className="relative flex items-center border border-border bg-background rounded-lg px-2">
                <Filter className="h-3 w-3 text-muted-foreground mr-1" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-transparent py-1.5 text-xs text-foreground outline-none cursor-pointer"
                >
                  <option value="all">All Status</option>
                  <option value="paid">Paid</option>
                  <option value="failed">Failed</option>
                  <option value="pending">Pending</option>
                </select>
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">
                  <th className="px-6 py-3.5">ID</th>
                  <th className="px-6 py-3.5">Date</th>
                  <th className="px-6 py-3.5">User Account Key</th>
                  <th className="px-6 py-3.5 text-center">Plan</th>
                  <th className="px-6 py-3.5 text-center">Amount</th>
                  <th className="px-6 py-3.5 text-center">Devices</th>
                  <th className="px-6 py-3.5 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredTransactions.length > 0 ? (
                  filteredTransactions.map((tx) => (
                    <tr key={tx.id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-foreground">{tx.id}</td>
                      <td className="px-6 py-4 text-muted-foreground">{tx.date}</td>
                      <td className="px-6 py-4 font-mono text-muted-foreground/80 tracking-tight">
                        {tx.accountKey.slice(0, 10)}...{tx.accountKey.slice(-10)}
                      </td>
                      <td className="px-6 py-4 text-center text-foreground font-medium">{tx.plan}</td>
                      <td className="px-6 py-4 text-center text-foreground font-semibold">₹{tx.amount}</td>
                      <td className="px-6 py-4 text-center text-muted-foreground">{tx.devices}</td>
                      <td className="px-6 py-4 text-center">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            tx.status === 'paid'
                              ? 'bg-green-500/10 text-green-500 border border-green-500/20'
                              : tx.status === 'failed'
                              ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                              : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                          }`}
                        >
                          {tx.status === 'paid' && <CheckCircle className="h-3 w-3" />}
                          {tx.status === 'failed' && <XCircle className="h-3 w-3" />}
                          {tx.status === 'pending' && <ClockIcon className="h-3 w-3" />}
                          {tx.status}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-muted-foreground font-medium">
                      No transactions found matching the filter criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Admin Footer */}
      <footer className="border-t border-border bg-card mt-auto py-5 text-center text-xs text-muted-foreground">
        <p>&copy; {new Date().getFullYear()} Stealthy Network Operations Dashboard. Authorized Personnel Only.</p>
      </footer>
    </div>
  )
}

function ClockIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
      {...props}
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

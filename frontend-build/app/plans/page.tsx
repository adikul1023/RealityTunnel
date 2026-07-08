import Link from 'next/link'
import { CheckCircle2, Zap } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

const features = [
  { label: 'Encrypted private network access', monthly: true, yearly: true },
  { label: 'No activity logs', monthly: true, yearly: true },
  { label: 'Anonymous account key login', monthly: true, yearly: true },
  { label: 'Windows client', monthly: true, yearly: true },
  { label: 'Android client', monthly: true, yearly: true },
  { label: 'Monthly data included', monthly: '30 GB', yearly: '40 GB' },
  { label: 'Additional data rate', monthly: '₹10/GB', yearly: '₹10/GB' },
  { label: 'Connected device slots', monthly: '3 devices', yearly: '5 devices' },
  { label: 'India & global infrastructure', monthly: true, yearly: true },
  { label: '2FA support', monthly: true, yearly: true },
  { label: 'Priority support', monthly: false, yearly: true },
  { label: 'Annual billing discount', monthly: false, yearly: 'Save ~18%' },
]

function FeatureCell({ value }: { value: boolean | string }) {
  if (value === true)
    return <CheckCircle2 className="h-4 w-4 text-primary mx-auto" aria-label="Included" />
  if (value === false)
    return <span className="text-muted-foreground text-lg leading-none mx-auto block text-center" aria-label="Not included">—</span>
  return <span className="text-sm text-foreground font-medium text-center block">{value}</span>
}

export default function PlansPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-5xl">
          {/* Header */}
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3 text-balance">
              Simple, honest pricing
            </h1>
            <p className="text-muted-foreground max-w-lg mx-auto text-pretty">
              All prices are in Indian Rupees. GST is included in the listed price — no surprises
              at checkout.
            </p>
          </div>

          {/* Pricing cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-12">
            {/* Monthly */}
            <div className="rounded-xl border border-border bg-card p-8 flex flex-col">
              <div className="mb-6">
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1">Monthly</p>
                <div className="flex items-end gap-1">
                  <span className="text-4xl font-bold text-foreground">₹69</span>
                  <span className="text-muted-foreground pb-1">/month</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">GST included</p>
              </div>

              <ul className="space-y-2.5 mb-8 flex-1">
                {['30 GB data per month', '3 connected device slots', 'All platform clients', 'Encrypted private access', 'No activity logs'].map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-foreground">
                    <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0" />
                    {f}
                  </li>
                ))}
                <li className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-muted/50 flex-shrink-0" />
                  Additional data at ₹10/GB
                </li>
              </ul>

              <Link
                href="/register"
                className="block text-center rounded-md border border-border px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted transition-colors"
              >
                Get started — Monthly
              </Link>
            </div>

            {/* Yearly */}
            <div className="rounded-xl border border-primary/40 bg-card p-8 flex flex-col relative overflow-hidden">
              <div className="absolute top-4 right-4 flex items-center gap-1 rounded-full bg-primary/15 border border-primary/30 px-2.5 py-0.5 text-xs font-medium text-primary">
                <Zap className="h-3 w-3" />
                Best value
              </div>

              <div className="mb-6">
                <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-1">Yearly</p>
                <div className="flex items-end gap-1">
                  <span className="text-4xl font-bold text-foreground">₹680</span>
                  <span className="text-muted-foreground pb-1">/year</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">GST included · ≈ ₹56.67/month</p>
              </div>

              <ul className="space-y-2.5 mb-8 flex-1">
                {['40 GB data per month', '5 connected device slots', 'All platform clients', 'Encrypted private access', 'No activity logs', 'Priority support'].map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-foreground">
                    <CheckCircle2 className="h-4 w-4 text-primary flex-shrink-0" />
                    {f}
                  </li>
                ))}
                <li className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-muted/50 flex-shrink-0" />
                  Additional data at ₹10/GB
                </li>
              </ul>

              <Link
                href="/register"
                className="block text-center rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Get started — Yearly
              </Link>
            </div>
          </div>

          {/* Comparison table */}
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <div className="border-b border-border px-6 py-4">
              <h2 className="font-semibold text-foreground">Full feature comparison</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Feature
                    </th>
                    <th className="text-center px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Monthly
                    </th>
                    <th className="text-center px-6 py-3 text-xs font-medium text-primary uppercase tracking-wider">
                      Yearly
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {features.map((row) => (
                    <tr key={row.label} className="hover:bg-muted/20 transition-colors">
                      <td className="px-6 py-3 text-foreground">{row.label}</td>
                      <td className="px-6 py-3">
                        <FeatureCell value={row.monthly} />
                      </td>
                      <td className="px-6 py-3">
                        <FeatureCell value={row.yearly} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="mt-6 text-xs text-center text-muted-foreground">
            All prices include GST. Data add-ons are billed immediately.
            See our{' '}
            <Link href="/legal/refund" className="text-primary hover:underline">
              Refund & Cancellation Policy
            </Link>
            .
          </p>
        </div>
      </main>

      <Footer />
    </div>
  )
}

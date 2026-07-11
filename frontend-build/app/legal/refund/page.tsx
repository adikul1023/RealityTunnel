'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Calculator, Info } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

// ─── Refund Calculator ────────────────────────────────────────────────────────
function RefundCalculator() {
  const ANNUAL_PRICE = 680
  const MONTHLY_ALLOWANCE_GB = 40
  const MAX_REFUND_PCT = 0.70 // 70% cap
  const ELIGIBILITY_DAYS = 15

  const [daysSincePurchase, setDaysSincePurchase] = useState(7)
  const [gbUsed, setGbUsed] = useState(5)

  const isEligible = daysSincePurchase <= ELIGIBILITY_DAYS
  const usedFraction = Math.min(gbUsed / MONTHLY_ALLOWANCE_GB, 1)
  // Prorate: refund reduces with data used; capped at 70% of annual price
  const grossRefund = ANNUAL_PRICE * (1 - usedFraction)
  const cappedRefund = Math.min(grossRefund, ANNUAL_PRICE * MAX_REFUND_PCT)
  const estimatedRefund = isEligible ? Math.max(0, cappedRefund) : 0

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="border-b border-border px-6 py-4 flex items-center gap-2">
        <Calculator className="h-5 w-5 text-primary" />
        <h2 className="font-semibold text-foreground">Refund Estimator</h2>
        <span className="ml-auto text-xs text-muted-foreground">Yearly plan only</span>
      </div>

      <div className="p-6 space-y-6">
        {/* Days since purchase */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label htmlFor="days-slider" className="text-sm font-medium text-foreground">
              Days since purchase
            </label>
            <span
              className={`text-sm font-semibold tabular-nums ${
                daysSincePurchase <= ELIGIBILITY_DAYS ? 'text-primary' : 'text-destructive'
              }`}
            >
              {daysSincePurchase} day{daysSincePurchase !== 1 ? 's' : ''}
            </span>
          </div>
          <input
            id="days-slider"
            type="range"
            min={1}
            max={30}
            value={daysSincePurchase}
            onChange={(e) => setDaysSincePurchase(Number(e.target.value))}
            className="w-full accent-primary cursor-pointer"
            aria-label="Days since purchase"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>1 day</span>
            <span className="text-primary font-medium">15-day window</span>
            <span>30 days</span>
          </div>
        </div>

        {/* GB used */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label htmlFor="gb-slider" className="text-sm font-medium text-foreground">
              Data used this month
            </label>
            <span className="text-sm font-semibold tabular-nums text-foreground">
              {gbUsed} GB of {MONTHLY_ALLOWANCE_GB} GB
            </span>
          </div>
          <input
            id="gb-slider"
            type="range"
            min={0}
            max={MONTHLY_ALLOWANCE_GB}
            value={gbUsed}
            onChange={(e) => setGbUsed(Number(e.target.value))}
            className="w-full accent-primary cursor-pointer"
            aria-label="GB used"
          />
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>0 GB</span>
            <span>{MONTHLY_ALLOWANCE_GB} GB</span>
          </div>
        </div>

        {/* Result */}
        <div
          className={`rounded-xl p-5 border transition-colors ${
            isEligible
              ? 'border-primary/30 bg-primary/8'
              : 'border-destructive/20 bg-destructive/8'
          }`}
        >
          {isEligible ? (
            <div className="flex items-end justify-between gap-4 flex-wrap">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Estimated refund</p>
                <p className="text-4xl font-bold text-foreground">
                  ₹{estimatedRefund.toFixed(0)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {estimatedRefund < ANNUAL_PRICE * MAX_REFUND_PCT
                    ? `Prorated based on ${gbUsed} GB used`
                    : `Capped at 70% of ₹${ANNUAL_PRICE} annual price`}
                </p>
              </div>
              <div className="text-right">
                <span className="inline-block rounded-full bg-primary/15 border border-primary/25 px-3 py-1 text-xs font-medium text-primary">
                  Within eligibility window
                </span>
                <p className="text-xs text-muted-foreground mt-2">
                  {ELIGIBILITY_DAYS - daysSincePurchase} day{ELIGIBILITY_DAYS - daysSincePurchase !== 1 ? 's' : ''} left to request
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <div>
                <p className="text-sm font-semibold text-destructive mb-0.5">Outside eligibility window</p>
                <p className="text-sm text-muted-foreground">
                  Refunds can only be requested within {ELIGIBILITY_DAYS} days of purchase. Your
                  purchase was {daysSincePurchase} days ago.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Disclaimer */}
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          <p>
            This calculator is an estimate only. Your actual refund amount is determined at the
            time of your request based on verified usage data. Payout arrives in 3–7 business
            days to your original payment method.
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function RefundPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Legal</p>
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3 text-balance">
              Refund &amp; Cancellation Policy
            </h1>
            <p className="text-sm text-muted-foreground">Last updated: 6 July 2026</p>
          </div>

          <div className="space-y-8">
            <LegalSection title="1. Plan eligibility">
              <ul className="space-y-2.5 text-sm text-muted-foreground">
                <li className="border-l-2 border-primary/40 pl-3">
                  <strong className="text-foreground">Yearly plan:</strong> Refunds are available
                  within the eligibility window described below.
                </li>
                <li className="border-l-2 border-border pl-3">
                  <strong className="text-foreground">Monthly plan:</strong> Monthly plans are
                  non-refundable once a billing cycle has started.
                </li>
              </ul>
            </LegalSection>

            <LegalSection title="2. Eligibility window">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Yearly plan subscribers may request a refund within{' '}
                <strong className="text-foreground">15 days</strong> of their purchase date. After
                15 days, no refund will be issued under any circumstances.
              </p>
            </LegalSection>

            <LegalSection title="3. How your refund is calculated">
              <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                Within the 15-day window, your refund amount is prorated based on how much of your
                monthly data allowance you have already used — up to a maximum of{' '}
                <strong className="text-foreground">70% of your annual payment</strong>. Use the
                calculator below to estimate your refund.
              </p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                <strong className="text-foreground">Formula:</strong> Estimated refund = Annual
                price × (1 − data used fraction), capped at 70% of ₹680.
              </p>
            </LegalSection>

            <LegalSection title="4. Payout timing">
              <p className="text-sm text-muted-foreground leading-relaxed">
                If you are eligible for a refund, you will receive it in{' '}
                <strong className="text-foreground">3–7 business days</strong> to your original
                payment method.
              </p>
            </LegalSection>

            <LegalSection title="5. Data add-ons">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Data add-on purchases (top-ups at ₹10/GB) are non-refundable once the data has been
                credited to your account. If a payment is charged but data is not credited due to a
                technical error, contact support within 7 days for a full refund or credit.
              </p>
            </LegalSection>

            <LegalSection title="6. How to request a refund">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Contact us through the{' '}
                <Link href="/faq" className="text-primary hover:underline">
                  FAQ &amp; Support page
                </Link>{' '}
                within the eligible window. Include your transaction reference ID (visible in your
                Billing History) and master token. Refunds are processed to the original payment
                method within 3–7 business days.
              </p>
            </LegalSection>

            <LegalSection title="7. Cancellation">
              <p className="text-sm text-muted-foreground leading-relaxed">
                You may cancel your subscription at any time by disabling auto-renew from your
                dashboard. Cancellation prevents future billing but does not terminate your current
                active period — you retain full access until the period you paid for ends.
              </p>
            </LegalSection>

            <LegalSection title="8. Service interruptions">
              <p className="text-sm text-muted-foreground leading-relaxed">
                If the service is unavailable for more than 72 consecutive hours due to a fault on
                our infrastructure (excluding scheduled maintenance or force majeure), you may
                request a prorated credit for the affected period. Credits are applied to your next
                billing cycle and are non-transferable.
              </p>
            </LegalSection>

            <LegalSection title="9. Changes to this policy">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We may update this policy from time to time. The policy in effect at the time of
                your purchase governs that transaction.
              </p>
            </LegalSection>

            {/* Calculator */}
            <div className="border-t border-border pt-8">
              <RefundCalculator />
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="text-base font-semibold text-foreground mb-3">{title}</h2>
      {children}
    </section>
  )
}

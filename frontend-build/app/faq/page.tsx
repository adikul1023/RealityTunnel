'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ChevronDown, ChevronUp, MessageCircle } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

const categories = [
  {
    label: 'Account & Security',
    questions: [
      {
        q: 'What happens if I lose my master token?',
        a: 'Your master token cannot be recovered under any circumstances. There is no email-based reset, no security question, and no support escalation path that can retrieve it. This is intentional — it means no one, including us, can gain access to your account by impersonating you. If you lose your token, you will need to create a new account. We strongly recommend copying your token to at least two secure, offline locations (for example, a password manager and a printed backup in a safe place).',
      },
      {
        q: 'How does the master token system work?',
        a: 'When you register, a 32-character alphanumeric token is generated in your browser. This token is the secret credential for your account — there is no associated email address, phone number, or personal identity. You use this token to log in across all devices. We store only a cryptographic hash of the token on our servers; your plaintext token is never transmitted after account creation.',
      },
      {
        q: 'Is two-factor authentication (2FA) available?',
        a: 'Yes. During registration you can optionally set up TOTP-based 2FA using any standard authenticator app (Google Authenticator, Aegis, Authy, etc.). You will also be given 8 one-time backup codes — save these separately from your master token, as they are your only fallback if you lose access to your authenticator device.',
      },
      {
        q: 'Can I have multiple accounts?',
        a: 'Yes. Since there is no email or personal identity linked to accounts, you may create as many accounts as you wish. Each requires a separate subscription and master token.',
      },
    ],
  },
  {
    label: 'Privacy & Data',
    questions: [
      {
        q: 'What data do you log?',
        a: 'For connections routed through our India-based infrastructure, applicable law requires us to retain: account registration information, login and logout timestamps for each session, and the IP address assigned to you during each session. We do not log the websites you visit, the content of your traffic, or your browsing activity. For connections routed through non-India infrastructure, no session-level metadata is retained. See our Privacy Policy for full details.',
      },
      {
        q: 'Do you sell my data to advertisers?',
        a: 'No. We do not sell, rent, or share your data with advertisers or data brokers. Our business model is subscription-based — we have no financial incentive to monetise your data.',
      },
      {
        q: 'Can you see the websites I visit?',
        a: 'No. We do not log, monitor, or have visibility into the specific websites or services you access through our network. Only connection metadata (when you connected and disconnected, and the IP address assigned for India-routed sessions) is retained where legally required.',
      },
      {
        q: 'What happens to my data if I delete my account?',
        a: 'Deleting your account removes your master token hash and subscription records from our active databases. Legally mandated connection metadata for India-routed sessions is retained for the period required by law, after which it is deleted. Payment records are retained as required by GST and tax law.',
      },
    ],
  },
  {
    label: 'Billing & Plans',
    questions: [
      {
        q: 'What does "GST included" mean for pricing?',
        a: 'Our listed prices (₹69/month, ₹99/month, ₹179/quarter, ₹10/GB) are the total amount you pay — GST is already factored in. There are no additional taxes added at checkout.',
      },
      {
        q: 'What happens when I run out of data?',
        a: 'When your monthly data allowance is exhausted, your encrypted connection will be paused until you purchase additional data or your next billing cycle begins. You can top up at any time from the My Credits dashboard at ₹10/GB.',
      },
      {
        q: 'Can I switch between monthly and quarterly plans?',
        a: 'Yes. You can upgrade or downgrade your plans from your dashboard. Upgrades take effect immediately. Downgrades take effect at the end of your current billing period.',
      },
      {
        q: 'How do I get a refund?',
        a: 'See our Refund & Cancellation Policy for the full terms. In summary: monthly plans are refundable within 48 hours (under 1 GB used), and yearly plans within 7 days (under 5 GB used). Data add-ons are non-refundable once added to your account.',
      },
    ],
  },
  {
    label: 'Technical',
    questions: [
      {
        q: 'Which platforms are supported?',
        a: 'We currently provide clients for Windows (10 and later, 64-bit) and Android (8.0 Oreo and later). Additional platform support may be added in future releases.',
      },
      {
        q: 'How many devices can I connect simultaneously?',
        a: 'The number of simultaneous device slots depends on your plan: 3 slots on the Monthly plan, and 5 slots on the Yearly plan. You can view and manage your connected devices from the My Devices dashboard.',
      },
      {
        q: 'What encryption does Stealthy use?',
        a: 'Stealthy uses industry-standard protocols for establishing the encrypted tunnel between your device and our servers. Specific protocol details are available in our technical documentation.',
      },
      {
        q: 'What should I do if I cannot connect?',
        a: 'First verify that your master token is entered correctly and that your subscription is active. Check your data balance on the My Credits page. If the issue persists, try selecting a different server region in the client. For further help, contact support through this page.',
      },
    ],
  },
]

function AccordionItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left hover:bg-muted/30 transition-colors"
        aria-expanded={open}
      >
        <span className="text-sm font-medium text-foreground leading-snug">{q}</span>
        {open
          ? <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
          : <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />}
      </button>
      {open && (
        <div className="px-5 pb-4">
          <p className="text-sm text-muted-foreground leading-relaxed">{a}</p>
        </div>
      )}
    </div>
  )
}

export default function FaqPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3 text-balance">
              FAQ &amp; Support
            </h1>
            <p className="text-muted-foreground max-w-lg mx-auto text-pretty">
              Common questions about Stealthy. If you cannot find an answer below, contact us directly.
            </p>
          </div>

          <div className="space-y-6 mb-12">
            {categories.map((cat) => (
              <div key={cat.label} className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="border-b border-border px-5 py-3.5 bg-muted/30">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{cat.label}</h2>
                </div>
                <div>
                  {cat.questions.map((item) => (
                    <AccordionItem key={item.q} q={item.q} a={item.a} />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Contact CTA */}
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15">
                <MessageCircle className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-semibold text-foreground">Still need help?</p>
                <p className="text-sm text-muted-foreground">
                  Join our Telegram support community — ask questions and get help from our team and other users.
                </p>
              </div>
            </div>
            <a
              href="https://t.me/stealthysupportcare"
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <MessageCircle className="h-4 w-4" />
              Join Support Group
            </a>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

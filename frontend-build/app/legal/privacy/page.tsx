import Link from 'next/link'
import { Shield, AlertTriangle } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

export default function PrivacyPolicyPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Legal</p>
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3">Privacy Policy</h1>
            <p className="text-sm text-muted-foreground">Last updated: 6 July 2026</p>
          </div>

          {/* Highlighted data retention callout — India infrastructure */}
          <section id="data-retention" className="mb-10 rounded-xl border-2 border-primary/40 bg-primary/5 p-6 scroll-mt-24">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 flex-shrink-0">
                <AlertTriangle className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">Data Retention — India-Based Infrastructure</h2>
                <p className="text-sm text-muted-foreground mt-0.5">This section is highlighted for easy access.</p>
              </div>
            </div>
            <div className="space-y-3 text-sm text-foreground leading-relaxed">
              <p>
                If you are routed through our India-based infrastructure, applicable Indian regulations require
                us to retain the following for a period as mandated by law:
              </p>
              <ul className="space-y-1.5 pl-4 border-l-2 border-primary/30">
                <li className="flex items-start gap-2">
                  <span className="text-primary mt-0.5">·</span>
                  Account registration information
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary mt-0.5">·</span>
                  Login and logout timestamps for each session
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary mt-0.5">·</span>
                  The IP address assigned to you during each session
                </li>
              </ul>
              <p className="font-medium text-foreground bg-primary/10 rounded-lg px-4 py-3 border border-primary/20">
                We do <strong>not</strong> log, monitor, or retain the specific websites you visit, the
                content of your traffic, or your browsing activity. Only connection metadata (when you
                connected and disconnected) is retained for our India-based infrastructure, as required
                by applicable law.
              </p>
              <p>
                Users routed through non-India infrastructure are <strong>not</strong> subject to this
                retention requirement.
              </p>
            </div>
          </section>

          <div className="prose prose-sm max-w-none space-y-8">
            <LegalSection title="1. Who we are">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Stealthy is a private network access service operated as a GST-registered entity in India.
                This Privacy Policy explains how we collect, use, and protect information when you use our
                services.
              </p>
            </LegalSection>

            <LegalSection title="2. Information we collect">
              <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                We collect the absolute minimum necessary to provide the service:
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><strong className="text-foreground">Account identifier:</strong> A randomly generated 32-character key created on your device. We never ask for your name, email, phone number, or any personal identifier.</li>
                <li><strong className="text-foreground">Payment information:</strong> Processed by our third-party payment gateway. We receive only a transaction reference and status — not your card or bank details.</li>
                <li><strong className="text-foreground">Connection metadata (India infrastructure only):</strong> As described in the Data Retention section above — session timestamps and the IP address assigned to you.</li>
                <li><strong className="text-foreground">Device identifiers:</strong> A device name and platform type to manage your device slots. You control this list and can remove devices at any time.</li>
              </ul>
            </LegalSection>

            <LegalSection title="3. What we do not collect">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We do not collect, log, monitor, or retain: the websites or services you access through our
                network; the content of any traffic passing through our servers; DNS queries made through
                our infrastructure; your real IP address when connecting through non-India infrastructure;
                or any behavioural, advertising, or analytics data.
              </p>
            </LegalSection>

            <LegalSection title="4. How we use your information">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Information collected is used solely to: authenticate your account, provision and manage your
                subscription, process payments, manage your connected devices, and comply with applicable
                legal obligations in India.
              </p>
            </LegalSection>

            <LegalSection title="5. Data sharing">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We do not sell, rent, or share your data with third parties for marketing or commercial purposes.
                Data may be disclosed to our payment processor (to process transactions), and to law enforcement
                authorities where we are legally compelled to do so under applicable Indian law. We will not
                voluntarily disclose data beyond what is legally required.
              </p>
            </LegalSection>

            <LegalSection title="6. Data security">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Master tokens are stored in a hashed form and cannot be recovered. Our servers use industry-standard
                encryption for data in transit and at rest. Access to infrastructure is restricted and logged.
              </p>
            </LegalSection>

            <LegalSection title="7. Data retention periods">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Connection metadata for India-routed sessions is retained for the period mandated by applicable
                Indian law. Account data (master token hash, subscription status) is retained for the lifetime
                of your account and for a reasonable period thereafter for billing dispute resolution. Payment
                transaction records are retained as required by GST and applicable tax law.
              </p>
            </LegalSection>

            <LegalSection title="8. Your rights">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Given the anonymous nature of our service, we have limited ability to link any request to a
                specific individual. You may request deletion of your account data by providing your account
                key via our support channel. We will confirm the data we hold associated with that key and
                action deletion where legally permissible.
              </p>
            </LegalSection>

            <LegalSection title="9. Changes to this policy">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We may update this policy to reflect changes in law or our practices. Material changes will
                be noted at the top of this page with a revised date. Continued use of the service after
                changes constitutes acceptance.
              </p>
            </LegalSection>

            <LegalSection title="10. Contact">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Privacy-related enquiries can be directed to our support channel via the{' '}
                <Link href="/faq" className="text-primary hover:underline">FAQ & Support page</Link>.
              </p>
            </LegalSection>
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

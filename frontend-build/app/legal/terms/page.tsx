import Link from 'next/link'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

export default function TermsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Legal</p>
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3">Terms of Service</h1>
            <p className="text-sm text-muted-foreground">Last updated: 6 July 2026</p>
          </div>

          <div className="space-y-8">
            <LegalSection title="1. Acceptance of terms">
              <p className="text-sm text-muted-foreground leading-relaxed">
                By creating an account or using Stealthy services, you agree to be bound by these Terms of
                Service. If you do not agree, do not use the service.
              </p>
            </LegalSection>

            <LegalSection title="2. Description of service">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Stealthy provides a private network access service that encrypts your internet traffic and
                routes it through our server infrastructure. The service is provided on a subscription basis.
                Access requires a valid 32-character account key and an active paid plan.
              </p>
            </LegalSection>

            <LegalSection title="3. Account key and authentication">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Your account key is your sole authentication credential. It is generated on your device and
                is your responsibility to store securely. Stealthy does not retain a copy of your plaintext
                account key and cannot recover it under any circumstances. Loss of your account key means
                permanent loss of access to the associated account and any remaining subscription period.
              </p>
            </LegalSection>

            <LegalSection title="4. Acceptable use">
              <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                You agree not to use Stealthy for any of the following:
              </p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                <li>· Activities that violate any applicable law or regulation in India or your jurisdiction</li>
                <li>· Distributing malware, conducting denial-of-service attacks, or engaging in network intrusion</li>
                <li>· Child sexual abuse material or any content that sexually exploits minors</li>
                <li>· Spamming, phishing, or other unsolicited communications</li>
                <li>· Circumventing access controls in ways that violate applicable computer crime laws</li>
              </ul>
            </LegalSection>

            <LegalSection title="5. Subscriptions and billing">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Subscriptions are available on monthly (₹69/month, GST included) and yearly (₹680/year,
                GST included) terms. Data add-ons are available at ₹10/GB (GST included). Billing is
                handled through our third-party payment gateway. For refund and cancellation terms, see our{' '}
                <Link href="/legal/refund" className="text-primary hover:underline">Refund &amp; Cancellation Policy</Link>.
              </p>
            </LegalSection>

            <LegalSection title="6. Data and privacy">
              <p className="text-sm text-muted-foreground leading-relaxed">
                Our data practices are described in detail in our{' '}
                <Link href="/legal/privacy" className="text-primary hover:underline">Privacy Policy</Link>,
                including the specific data retention obligations that apply to India-based infrastructure
                under applicable Indian law.
              </p>
            </LegalSection>

            <LegalSection title="7. Service availability">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We aim for high availability but do not guarantee uninterrupted service. Scheduled
                maintenance, infrastructure issues, or circumstances outside our control may result in
                temporary unavailability. We do not provide prorated refunds for service interruptions
                unless they exceed 72 consecutive hours.
              </p>
            </LegalSection>

            <LegalSection title="8. Termination">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We reserve the right to suspend or terminate accounts that violate these Terms. You may
                cancel your subscription at any time, subject to the terms in our Refund &amp; Cancellation
                Policy. On termination, your account key is invalidated and access is revoked.
              </p>
            </LegalSection>

            <LegalSection title="9. Limitation of liability">
              <p className="text-sm text-muted-foreground leading-relaxed">
                To the maximum extent permitted by applicable law, Stealthy shall not be liable for any
                indirect, incidental, special, consequential, or punitive damages arising from use of the
                service. Our total liability to you for any claim arising from the service shall not exceed
                the amount you paid in the three months preceding the claim.
              </p>
            </LegalSection>

            <LegalSection title="10. Governing law">
              <p className="text-sm text-muted-foreground leading-relaxed">
                These Terms are governed by the laws of India. Disputes shall be subject to the exclusive
                jurisdiction of the competent courts in India.
              </p>
            </LegalSection>

            <LegalSection title="11. Changes to these terms">
              <p className="text-sm text-muted-foreground leading-relaxed">
                We may update these Terms from time to time. Material changes will be noted with a revised
                date at the top of this page. Continued use of the service after changes constitutes acceptance
                of the updated Terms.
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

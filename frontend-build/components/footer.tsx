import Link from 'next/link'
import { StealthyLogo } from '@/components/ui/logo'

export function Footer() {
  return (
    <footer className="border-t border-border bg-card mt-auto">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-3">
              <StealthyLogo className="h-6 w-6" />
              <span className="font-semibold text-foreground">Stealthy</span>
            </Link>
            <p className="text-xs text-muted-foreground leading-relaxed max-w-xs">
              Encrypted, private network access. No activity logs. Anonymous account-key
              authentication.
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Product
            </p>
            <ul className="space-y-2">
              <li><Link href="/plans" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Plans &amp; Pricing</Link></li>
              <li><Link href="/downloads" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Downloads</Link></li>
              <li><Link href="/faq" className="text-sm text-muted-foreground hover:text-foreground transition-colors">FAQ &amp; Support</Link></li>
            </ul>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Account
            </p>
            <ul className="space-y-2">
              <li><Link href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Log In</Link></li>
              <li><Link href="/register" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Create Account</Link></li>
            </ul>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Legal
            </p>
            <ul className="space-y-2">
              <li><Link href="/legal/terms" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Terms of Service</Link></li>
              <li><Link href="/legal/privacy" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Privacy Policy</Link></li>
              <li><Link href="/legal/refund" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Refund Policy</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} Stealthy. All rights reserved. GST registered entity.
          </p>
          <p className="text-xs text-muted-foreground">
            India-based infrastructure subject to data retention requirements.{' '}
            <Link href="/legal/privacy#data-retention" className="text-primary hover:underline">
              Learn more
            </Link>
          </p>
        </div>
      </div>
    </footer>
  )
}

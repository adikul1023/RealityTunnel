'use client'

import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/api'

interface PlanCtaProps {
  planId: string
  label?: string
  variant?: 'default' | 'primary'
}

/**
 * Plan call-to-action button.
 *
 * Authenticated users → /dashboard (payments not yet enabled).
 * Unauthenticated users → /register
 *
 * When payments are enabled, replace the authenticated branch with:
 *   router.push(`/checkout?plan=${planId}`)
 */
export function PlanCta({ planId, label = 'Get started', variant = 'default' }: PlanCtaProps) {
  const router = useRouter()

  function handleClick() {
    if (isAuthenticated()) {
      // Pass the selected plan to the dashboard so the payment modal
      // can pre-select and show the correct QR code.
      router.push(`/dashboard?pay=${planId}`)
    } else {
      router.push('/register')
    }
  }

  const className =
    variant === 'primary'
      ? 'block w-full text-center rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer'
      : 'block w-full text-center rounded-md border border-border px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted transition-colors cursor-pointer'

  return (
    <button type="button" onClick={handleClick} className={className}>
      {label}
    </button>
  )
}

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
export function PlanCta({ planId, label = 'Subscriptions Paused', variant = 'default' }: PlanCtaProps) {
  const router = useRouter()

  function handleClick() {
    // Navigates to dashboard where the pause notice modal is displayed
    router.push(`/dashboard?pay=${planId}`)
  }

  const className =
    variant === 'primary'
      ? 'block w-full text-center rounded-md bg-muted text-muted-foreground border border-border px-4 py-2.5 text-sm font-semibold hover:bg-muted/80 transition-colors cursor-pointer'
      : 'block w-full text-center rounded-md border border-border text-muted-foreground px-4 py-2.5 text-sm font-semibold hover:bg-muted/50 transition-colors cursor-pointer'

  return (
    <button type="button" onClick={handleClick} className={className}>
      {label}
    </button>
  )
}

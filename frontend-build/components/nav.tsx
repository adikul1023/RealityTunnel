'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { Shield, Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const publicLinks = [
  { href: '/plans', label: 'Plans' },
  { href: '/downloads', label: 'Downloads' },
  { href: '/faq', label: 'Support' },
]

const authLinks = [
  { href: '/dashboard/credits', label: 'My Credits' },
  { href: '/dashboard/devices', label: 'Devices' },
  { href: '/dashboard/billing', label: 'Billing' },
]

export function Nav({ isLoggedIn = false }: { isLoggedIn?: boolean }) {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  const links = isLoggedIn ? [...publicLinks, ...authLinks] : publicLinks

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/30 group-hover:bg-primary/25 transition-colors">
              <Shield className="h-4 w-4 text-primary" />
            </div>
            <span className="font-semibold tracking-tight text-foreground">NullRoute</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'px-3 py-1.5 text-sm rounded-md transition-colors',
                  pathname === link.href
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Auth buttons */}
          <div className="hidden md:flex items-center gap-2">
            {isLoggedIn ? (
              <Link
                href="/"
                className="px-3 py-1.5 text-sm rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                Sign Out
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-3 py-1.5 text-sm rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  Log In
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-1.5 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 font-medium transition-colors"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden text-muted-foreground hover:text-foreground"
            onClick={() => setOpen(!open)}
            aria-label="Toggle menu"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {/* Mobile nav */}
        {open && (
          <div className="md:hidden pb-4 pt-2 space-y-1 border-t border-border mt-0">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={cn(
                  'block px-3 py-2 text-sm rounded-md transition-colors',
                  pathname === link.href
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-2 flex flex-col gap-1">
              {isLoggedIn ? (
                <Link
                  href="/"
                  onClick={() => setOpen(false)}
                  className="px-3 py-2 text-sm rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  Sign Out
                </Link>
              ) : (
                <>
                  <Link
                    href="/login"
                    onClick={() => setOpen(false)}
                    className="px-3 py-2 text-sm rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
                  >
                    Log In
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setOpen(false)}
                    className="px-3 py-2 text-sm rounded-md bg-primary text-primary-foreground font-medium"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </header>
  )
}

import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Stealthy — Secure Private Network Access',
  description:
    'Stealthy provides encrypted, private network access with no activity logs. Anonymous master-token authentication, no email required.',
  generator: 'v0.app',
  keywords: [
    'secure connection',
    'private network access',
    'encrypted tunnel',
    'privacy layer',
    'anonymous',
  ],
  other: {
    'darkreader-lock': 'true',
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#0a0f14',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="bg-background" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`} suppressHydrationWarning>
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}

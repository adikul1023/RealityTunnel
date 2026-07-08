import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'NullRoute — Secure Private Network Access',
  description:
    'NullRoute provides encrypted, private network access with no activity logs. Anonymous account-key authentication, no email required.',
  generator: 'v0.app',
  keywords: [
    'secure connection',
    'private network access',
    'encrypted tunnel',
    'privacy layer',
    'anonymous',
  ],
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
    <html lang="en" className="bg-background">
      <body className={`${inter.className} antialiased`}>
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}

import Link from 'next/link'
import { Shield, Lock, Wifi, Server, ChevronRight } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

const features = [
  {
    icon: Lock,
    title: 'End-to-End Encrypted Tunnel',
    description:
      'All traffic between your device and our servers is wrapped in encryption. Nobody intercepts your data in transit — not even us.',
  },
  {
    icon: Wifi,
    title: 'Private Network Access',
    description:
      'Route your internet traffic through our encrypted infrastructure. Your real IP address is replaced with ours for every session.',
  },
  {
    icon: Shield,
    title: 'Anonymous Account System',
    description:
      'No email, no phone number, no personal details. Your account is a 32-character key. There is no recovery — privacy by design.',
  },
  {
    icon: Server,
    title: 'Multi-Device Support',
    description:
      'Connect your laptop, phone, or tablet. Your plan includes a defined number of concurrent device slots — add or remove devices any time.',
  },
]

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col" suppressHydrationWarning>
      <Nav />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative pt-32 pb-24 px-4 sm:px-6 overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage:
                'linear-gradient(oklch(0.72 0.16 195) 1px, transparent 1px), linear-gradient(90deg, oklch(0.72 0.16 195) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
            }}
            aria-hidden="true"
            suppressHydrationWarning
          />
          <div
            className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] rounded-full blur-[140px] opacity-10"
            style={{ background: 'oklch(0.72 0.16 195)' }}
            aria-hidden="true"
            suppressHydrationWarning
          />

          <div className="relative mx-auto max-w-4xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary mb-6">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
              </span>
              System active — encrypted connections available
            </div>

            <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-foreground text-balance leading-tight mb-6">
              Your traffic,{' '}
              <span className="text-primary">private and encrypted</span>
            </h1>

            <p className="text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed mb-10 text-pretty">
              Stealthy provides a secure, encrypted tunnel for your internet traffic. No email.
              No personal data. Anonymous master-token authentication — your identity stays yours.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Create Account
                <ChevronRight className="h-4 w-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                Log In
              </Link>
              <Link
                href="/plans"
                className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                View plans →
              </Link>
            </div>
          </div>
        </section>


        {/* Features */}
        <section className="py-24 px-4 sm:px-6">
          <div className="mx-auto max-w-7xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold tracking-tight text-foreground mb-3 text-balance">
                Built for genuine privacy
              </h2>
              <p className="text-muted-foreground max-w-xl mx-auto text-pretty">
                Every design decision favours your privacy. We collect the minimum required by law
                and nothing more.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {features.map((f) => (
                <div
                  key={f.title}
                  className="rounded-xl border border-border bg-card p-6 hover:border-primary/30 transition-colors"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-4">
                    <f.icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-semibold text-foreground mb-2">{f.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{f.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="py-24 px-4 sm:px-6 bg-muted/20 border-y border-border">
          <div className="mx-auto max-w-5xl">
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold tracking-tight text-foreground mb-3 text-balance">
                How it works
              </h2>
              <p className="text-muted-foreground text-pretty">
                Three steps to a private, encrypted connection.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
              {[
                {
                  step: '01',
                  title: 'Generate your master token',
                  desc: 'A 32-character alphanumeric token is generated in your browser. No email, no password — save it somewhere secure.',
                },
                {
                  step: '02',
                  title: 'Choose a plan',
                  desc: 'Pick monthly or yearly. All pricing is in INR and includes GST. Pay once and get access immediately.',
                },
                {
                  step: '03',
                  title: 'Install and connect',
                  desc: 'Download the client for Windows or Android. Enter your master token and establish a secure private network connection.',
                },
              ].map((item) => (
                <div key={item.step}>
                  <div className="text-5xl font-bold text-primary/20 mb-3 font-mono">{item.step}</div>
                  <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="py-24 px-4 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-foreground mb-4 text-balance">
              Ready to go private?
            </h2>
            <p className="text-muted-foreground mb-8 text-pretty">
              Start for ₹55/month. No personal information required. Cancel any time.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Create Account
                <ChevronRight className="h-4 w-4" />
              </Link>
              <Link
                href="/plans"
                className="inline-flex items-center gap-2 rounded-md border border-border px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                View Plans
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

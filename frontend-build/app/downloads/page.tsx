'use client'

import { Monitor, Smartphone, Download, CheckCircle2 } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'

// TODO: connect to backend API — replace with real download links
function MockDownloadButton({ label }: { label: string }) {
  return (
    <button
      type="button"
      onClick={() => alert('TODO: connect to backend API — download link not yet available')}
      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      <Download className="h-4 w-4" />
      {label}
    </button>
  )
}

const platforms = [
  {
    icon: Monitor,
    name: 'Windows',
    version: 'v2.4.1',
    requirements: 'Windows 10 or later (64-bit)',
    size: '~18 MB',
    steps: [
      'Download the installer (.exe) and run it.',
      'Accept the license agreement and complete installation.',
      'Launch NullRoute from your Start menu or desktop shortcut.',
      'Enter your 32-character account key when prompted.',
      'Select a server region and click Connect.',
    ],
    downloads: [
      { label: 'Installer (.exe)', sublabel: '~18 MB' },
      { label: 'Portable (.zip)', sublabel: '~20 MB' },
    ],
  },
  {
    icon: Smartphone,
    name: 'Android',
    version: 'v2.3.8',
    requirements: 'Android 8.0 (Oreo) or later',
    size: '~12 MB',
    steps: [
      'Download the APK file to your Android device.',
      'Enable "Install from unknown sources" in your device settings if prompted.',
      'Open the downloaded APK and follow the installation prompts.',
      'Launch NullRoute and enter your 32-character account key.',
      'Grant VPN permissions when the system dialog appears, then tap Connect.',
    ],
    downloads: [
      { label: 'APK (arm64-v8a)', sublabel: '~12 MB' },
      { label: 'APK (armeabi-v7a)', sublabel: '~11 MB' },
    ],
  },
]

export default function DownloadsPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />

      <main className="flex-1 pt-24 pb-20 px-4 sm:px-6">
        <div className="mx-auto max-w-4xl">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3 text-balance">
              Downloads &amp; Setup
            </h1>
            <p className="text-muted-foreground max-w-lg mx-auto text-pretty">
              Download the NullRoute client for your platform. You will need an active account key
              to connect.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {platforms.map((p) => (
              <div
                key={p.name}
                className="rounded-xl border border-border bg-card overflow-hidden flex flex-col"
              >
                {/* Header */}
                <div className="border-b border-border p-6 flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                    <p.icon className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-semibold text-foreground text-lg">{p.name}</h2>
                      <span className="text-xs rounded-full border border-border px-2 py-0.5 text-muted-foreground font-mono">
                        {p.version}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {p.requirements} · {p.size}
                    </p>
                  </div>
                </div>

                {/* Downloads */}
                <div className="p-6 border-b border-border space-y-3">
                  {p.downloads.map((dl) => (
                    <div key={dl.label} className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm font-medium text-foreground">{dl.label}</p>
                        <p className="text-xs text-muted-foreground">{dl.sublabel}</p>
                      </div>
                      <MockDownloadButton label="Download" />
                    </div>
                  ))}
                </div>

                {/* Setup steps */}
                <div className="p-6 flex-1">
                  <h3 className="text-sm font-semibold text-foreground mb-3">Setup instructions</h3>
                  <ol className="space-y-2.5">
                    {p.steps.map((step, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 mt-0.5">
                          <span className="text-[10px] font-bold text-primary">{i + 1}</span>
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed">{step}</p>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            ))}
          </div>

          {/* Linux — coming soon */}
          <div className="rounded-xl border border-dashed border-border bg-card/50 p-6 flex items-center gap-5 mb-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted flex-shrink-0">
              <Monitor className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h2 className="font-semibold text-foreground text-lg">Linux</h2>
                <span className="rounded-full bg-muted border border-border px-2.5 py-0.5 text-xs text-muted-foreground font-medium">
                  Coming soon
                </span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                A native Linux client is currently in development. Support for Debian/Ubuntu
                (apt), Fedora (rpm), and Arch is planned. Check back or watch our release notes
                for updates.
              </p>
            </div>
          </div>

          {/* No account note */}
          <div className="rounded-xl border border-border bg-muted/30 p-5 flex items-start gap-3">
            <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground mb-1">No account yet?</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                You need an active account and subscription to connect. Creating an account takes
                under a minute — no email required.{' '}
                <a href="/register" className="text-primary hover:underline">
                  Generate your account key →
                </a>
              </p>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}

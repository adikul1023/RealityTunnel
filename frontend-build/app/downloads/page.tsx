'use client'

import { useState, useEffect } from 'react'
import { Monitor, Smartphone, Download, CheckCircle2 } from 'lucide-react'
import { Nav } from '@/components/nav'
import { Footer } from '@/components/footer'
import { config } from '@/lib/config'

function DownloadButton({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
    >
      <Download className="h-4 w-4" />
      {label}
    </a>
  )
}

const windowsPlatform = {
  icon: Monitor,
  name: 'Windows',
  version: 'v1.1.2',
  requirements: 'Windows 10 or later (64-bit)',
  size: '88.8 MB',
  steps: [
    'Download the installer (setup.exe) and run it.',
    'Accept the license agreement and complete installation.',
    'Launch Stealthy from your Start menu or desktop shortcut.',
    'Enter your 32-character master token when prompted.',
    'Select a server region and click Connect.',
    'Troubleshooting: If it fails to connect or the exit IP shows as "?", open Task Manager, kill "Reality Tunnel" and "Reality Tunnel Helper", then try again.',
  ],
  downloads: [
    { label: 'Windows Installer', sublabel: 'setup.exe (88.8 MB)', href: 'https://github.com/adikul1023/StealthyDownloads/releases/latest/download/setup.exe' },
  ],
}

const androidPlatform = {
  icon: Smartphone,
  name: 'Android',
  version: 'v1.1.2',
  requirements: 'Android 8.0 (Oreo) or later',
  size: '55.6 MB',
  steps: [
    'Download the APK file (app-release.apk) to your Android device.',
    'Open Settings → Security (or Privacy) and enable "Install from unknown sources" for your browser or file manager.',
    'Open the downloaded APK and tap Install.',
    'Launch Stealthy from your app drawer.',
    'Enter your 32-character master token when prompted.',
    'Select a server region and tap Connect.',
  ],
  downloads: [
    { label: 'Android APK', sublabel: 'app-release.apk (55.6 MB)', href: 'https://github.com/adikul1023/StealthyDownloads/releases/latest/download/app-release.apk' },
  ],
}

export default function DownloadsPage() {
  const [release, setRelease] = useState({ version: 'v1.1.2', apkSize: '55.6 MB', exeSize: '88.8 MB' })

  useEffect(() => {
    fetch('https://api.github.com/repos/adikul1023/RealityTunnel/releases/latest')
      .then((res) => res.json())
      .then((data) => {
        if (!data.tag_name) return
        const apk = data.assets?.find((a: any) => a.name === 'app-release.apk')
        const exe = data.assets?.find((a: any) => a.name === 'setup.exe')
        setRelease({
          version: data.tag_name,
          apkSize: apk ? (apk.size / 1048576).toFixed(1) + ' MB' : '55.6 MB',
          exeSize: exe ? (exe.size / 1048576).toFixed(1) + ' MB' : '88.8 MB',
        })
      })
      .catch(() => {})
  }, [])

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
              Download the OverREALITY client for your platform. You will need an active master token
              to connect.
            </p>
          </div>

          {/* Windows — active */}
          <div className="rounded-xl border border-border bg-card overflow-hidden flex flex-col mb-6">
            {/* Header */}
            <div className="border-b border-border p-6 flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <windowsPlatform.icon className="h-6 w-6 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-foreground text-lg">{windowsPlatform.name}</h2>
                  <span className="text-xs rounded-full border border-border px-2 py-0.5 text-muted-foreground font-mono">
                    {release.version}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {windowsPlatform.requirements} · {release.exeSize}
                </p>
              </div>
            </div>

            {/* Downloads */}
            <div className="p-6 border-b border-border space-y-3">
              {windowsPlatform.downloads.map((dl) => (
                <div key={dl.label} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">{dl.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {dl.sublabel.includes('setup.exe') ? `setup.exe (${release.exeSize})` : dl.sublabel}
                    </p>
                  </div>
                  <DownloadButton href={dl.href} label="Download" />
                </div>
              ))}
            </div>

            {/* Setup steps */}
            <div className="p-6 flex-1">
              <h3 className="text-sm font-semibold text-foreground mb-3">Setup instructions</h3>
              <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-foreground">
                <strong>Note:</strong> The application may crash the first time you try to connect. If this happens, open Task Manager, end the &quot;Reality Tunnel&quot; and &quot;Reality Tunnel Helper&quot; tasks, and try again.
              </div>
              <ol className="space-y-2.5">
                {windowsPlatform.steps.map((step, i) => (
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

          {/* Android — active */}
          <div className="rounded-xl border border-border bg-card overflow-hidden flex flex-col mb-6">
            {/* Header */}
            <div className="border-b border-border p-6 flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <androidPlatform.icon className="h-6 w-6 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-foreground text-lg">{androidPlatform.name}</h2>
                  <span className="text-xs rounded-full border border-border px-2 py-0.5 text-muted-foreground font-mono">
                    {release.version}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {androidPlatform.requirements} · {release.apkSize}
                </p>
              </div>
            </div>

            {/* Downloads */}
            <div className="p-6 border-b border-border space-y-3">
              {androidPlatform.downloads.map((dl) => (
                <div key={dl.label} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">{dl.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {dl.sublabel.includes('app-release.apk') ? `app-release.apk (${release.apkSize})` : dl.sublabel}
                    </p>
                  </div>
                  <DownloadButton href={dl.href} label="Download" />
                </div>
              ))}
            </div>

            {/* Setup steps */}
            <div className="p-6 flex-1">
              <h3 className="text-sm font-semibold text-foreground mb-3">Setup instructions</h3>
              <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm text-foreground">
                <strong>Note:</strong> This is a sideloaded APK — not distributed via the Play Store.
                You will need to allow installation from unknown sources in your Android settings before installing.
              </div>
              <ol className="space-y-2.5">
                {androidPlatform.steps.map((step, i) => (
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

          {/* Coming Soon: Linux */}
          <div className="grid grid-cols-1 gap-4 mb-6">
            <div className="rounded-xl border border-dashed border-border bg-card/50 p-6 flex items-center gap-5">
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
                  A native Linux client is in development. Support for Debian/Ubuntu, Fedora, and Arch is planned.
                </p>
              </div>
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
                  Generate your master token →
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

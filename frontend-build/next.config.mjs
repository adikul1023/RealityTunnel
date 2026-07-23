/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ['admin.lvh.me', 'admin.localhost'],
  // Required for Next.js 16 — silences Turbopack/webpack config conflict error
  turbopack: {},
}

export default nextConfig

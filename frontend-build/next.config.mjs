/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ['admin.lvh.me', 'admin.localhost'],
  webpack: (config, { isServer }) => {
    // Ignore large binary files and archives in the workspace root that
    // confuse Turbopack's file watcher and cause repeated panics
    config.watchOptions = {
      ...config.watchOptions,
      ignored: [
        '**/node_modules/**',
        '**/.git/**',
        '**/*.zip',
        '**/*.rar',
        '**/*.apk',
        '**/*.tar.gz',
        '**/frontend-build*/**',
      ],
    }
    return config
  },
}

export default nextConfig

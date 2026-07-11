import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone()
  const hostname = request.headers.get('host') || ''

  // Checks if the host starts with the admin subdomain (e.g. admin.localhost:3000)
  const isCorrectSubdomain = hostname.toLowerCase().startsWith('admin.')

  if (isCorrectSubdomain) {
    // Avoid double rewrites to prevent infinite loops
    if (!url.pathname.startsWith('/admin')) {
      url.pathname = `/admin${url.pathname}`
      return NextResponse.rewrite(url)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - api (API routes)
     * - _next/static (Next.js static assets)
     * - _next/image (image optimization assets)
     * - logo.jpg, favicon.ico (root public files)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|logo.jpg).*)',
  ],
}

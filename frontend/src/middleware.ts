import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// This is a foundation for future cookie‑based auth.
// For now, it doesn't block anything because tokens are in localStorage,
// but it sets up the structure for when you switch to httpOnly cookies.
export function middleware(request: NextRequest) {
  // Example: check for access_token cookie
  // const token = request.cookies.get('access_token')?.value;
  // if (!token && request.nextUrl.pathname.startsWith('/dashboard')) {
  //   return NextResponse.redirect(new URL('/login', request.url));
  // }
  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
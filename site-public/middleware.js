import { NextResponse } from 'next/server';

function unauthorized() {
  return new Response('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Secure Area"',
      'Cache-Control': 'no-store'
    }
  });
}

export function middleware(req) {
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASS;

  // Fail closed if env is missing
  if (!user || !pass) return unauthorized();

  const auth = req.headers.get('authorization') || '';
  if (!auth.startsWith('Basic ')) return unauthorized();

  try {
    const base64 = auth.split(' ')[1] || '';
    const [u, p] = atob(base64).split(':');
    if (u === user && p === pass) return NextResponse.next();
  } catch (_) {
    // ignore parse errors
  }

  return unauthorized();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
};

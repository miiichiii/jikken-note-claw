function unauthorized() {
  return new Response('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Secure Area"',
      'Cache-Control': 'no-store'
    }
  });
}

export default function middleware(request) {
  const user = process.env.BASIC_AUTH_USER;
  const pass = process.env.BASIC_AUTH_PASS;

  // Fail closed if env is missing
  if (!user || !pass) return unauthorized();

  const auth = request.headers.get('authorization') || '';
  if (!auth.startsWith('Basic ')) return unauthorized();

  try {
    const base64 = auth.slice(6);
    const [u, p] = atob(base64).split(':');
    if (u === user && p === pass) {
      // allow request to continue
      return;
    }
  } catch (_e) {
    // ignore parse errors
  }

  return unauthorized();
}

export const config = {
  matcher: '/:path*'
};

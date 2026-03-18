function unauthorized(reason) {
  return new Response('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Secure Area"',
      'Cache-Control': 'no-store',
      'X-Auth-Fail-Reason': reason
    }
  });
}

export default function middleware(request) {
  const user = (process.env.BASIC_AUTH_USER || '').trim();
  const pass = (process.env.BASIC_AUTH_PASS || '').trim();

  // Fail closed if env is missing
  if (!user || !pass) return unauthorized('env-missing');

  const auth = request.headers.get('authorization') || '';
  if (!auth.startsWith('Basic ')) return unauthorized('no-auth-header');

  try {
    const base64 = auth.slice(6).trim();
    const decoded = atob(base64);
    const colonIndex = decoded.indexOf(':');
    if (colonIndex === -1) return unauthorized('no-colon');
    
    const u = decoded.slice(0, colonIndex);
    const p = decoded.slice(colonIndex + 1);
    
    if (p === pass) {
      // allow request to continue
      return;
    }
    return unauthorized('invalid-credentials');
  } catch (e) {
    return unauthorized('error-parsing:' + e.message);
  }
}

export const config = {
  matcher: '/:path*',
  runtime: 'edge'
};

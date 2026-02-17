# Vercel deployment (private-ish with auth)

## Goal
- Publish this site with a browser URL
- Require login before viewing (Vercel Deployment Protection)
- Keep it out of search engines

## Already configured in repo
- `robots.txt` disallow all
- `<meta name="robots" content="noindex, nofollow">` in `index.html`
- `vercel.json` sets `X-Robots-Tag: noindex, nofollow`

## Final setup (one-time in Vercel)
1. Import GitHub repo: `miiichiii/jikken-note-claw`
2. Deploy project
3. In Vercel project settings, enable **Deployment Protection** (Authentication / password protected access)
4. Restrict to only your account/team as needed
5. Use generated Vercel URL for access

> Note: `noindex` reduces search indexing, but true access control is Deployment Protection.

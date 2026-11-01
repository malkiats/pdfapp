# ADR-0003: Authentication: Supabase Auth, with stateless anonymous sessions

Status: accepted, deferred to Phase 7 · Date: 2026-10-31 · 2026-11-01 note: no accounts before Phase 7. Until then anonymous users get no cookie or session; abuse control is by rate limits (ADR-0006). Accounts and payments require leaving the Vercel Hobby plan, which is non-commercial only. The auth API must live apart from the tool functions (architecture.md §2).

## Context
Most usage is anonymous (free tier, no account). Accounts exist only for paid plans and their quotas. We need email plus OAuth login, a Next.js-friendly SDK, low cost at low MAU, JWTs the FastAPI backend can verify on its own, and as little personal data stored as possible.

## Decision
- **Supabase Auth** (managed, Singapore region) for registered users: email magic link or password, and Google OAuth.
  - The frontend uses `@supabase/ssr` with cookie-based sessions.
  - The API receives `Authorization: Bearer <access token>` and verifies it **locally against the project JWKS**, using asymmetric signing keys. It checks `iss`, `aud`, `exp` and the algorithm allowlist. The JWKS is cached and refreshed when a key id is unknown.
  - The shared JWT secret is never used.
  - The service-role key is used only by the backend (if ever), and is never exposed to the frontend.
- The same Supabase project's Postgres hosts schema `app` (table design owned by database-engineer). RLS is enabled with deny-all for `anon` and `authenticated` on `app.*`. Only the backend role reads and writes it.
- **Anonymous users do not get a Supabase account.** The API issues an `anon_sid` cookie: random id plus HMAC, `HttpOnly; Secure; SameSite=Lax; Domain=<apex>`, 24 h. It is used only for quota and rate-limit counters in Redis. Supabase "anonymous sign-ins" are not used, because they create persistent user rows.
- Frontend (`app.<apex>`) and API (`api.<apex>`) share a registrable domain, so cookies are same-site.

## Consequences
- (+) No auth server to run. The free tier covers the expected early MAU. The API needs no network call per request.
- (+) Auth and app data are in one vendor and one region.
- (−) Vendor coupling. This is contained to JWT verification plus the frontend SDK, and could be swapped for any OIDC provider.
- (−) Supabase stores auth logs (IP, user agent). This must be disclosed (privacy.md).

## Rejected
- **Clerk**: excellent DX, but per-MAU pricing and another processor.
- **Auth.js / self-hosted**: we would own session storage and the security patches.
- **Keycloak**: ops-heavy for this team.
- **Cognito**: weaker DX, and only worth it if we fully commit to AWS.

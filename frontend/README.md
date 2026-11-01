# Frontend (Next.js)

Marketing site and tool UI for the privacy-first document tools service. Next.js 16 (App Router, React Server
Components, Cache Components), TypeScript (strict), Tailwind CSS v4, lucide-react, next-themes.

Phase 1 scope: homepage, tool catalog pages (statically generated from `shared/tool-catalog.json`), pricing,
about, contact, security, draft legal shells and account stubs. No document processing yet: every tool is
`coming_soon` in the catalog, so upload areas are rendered disabled.

## Requirements

- Node.js 24 LTS (`engines: >=24`; the repo root pins `.nvmrc`). npm (lockfile: `package-lock.json`).

## Commands

| Command | What it does |
|---|---|
| `npm ci` | Install exact dependencies |
| `npm run dev` | Dev server on <http://localhost:3000> |
| `npm run build` | Production build (all pages prerendered) |
| `npm run start` | Serve the production build on port 3000 (`-p` / `PORT` to change) |
| `npm run lint` | ESLint (Next core-web-vitals + TypeScript rules), zero warnings allowed |
| `npm run typecheck` | `tsc --noEmit` (run `npm run build` or `npx next typegen` first on a fresh clone so route types exist) |
| `npm test` | Vitest + React Testing Library unit/component tests |
| `npm run test:e2e` | Playwright smoke tests. Builds are not automatic: run `npm run build` first. Starts `next start` on port 3100 |
| `npm run api:types` | Regenerate `src/lib/api/schema.d.ts` from `../shared/openapi.yaml` (commit the result; CI diffs it) |

First Playwright run on a machine: `npx playwright install chromium` (CI: `npx playwright install --with-deps chromium`).

## Environment variables

Copy `.env.example` to `.env.local`. Only public, non-secret values belong here; everything is inlined into the
browser bundle at build time, so a change needs a rebuild.

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | Canonical origin: `metadataBase`, canonical links, Open Graph URLs, sitemap, robots |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Document API base URL for the typed client, and the only extra origin in the CSP `connect-src` |

Both must be absolute `http(s)` URLs; the build fails otherwise. To develop against the API mock, run
`npx -y @stoplight/prism-cli@5.16.0 mock ../shared/openapi.yaml -p 4010` and set
`NEXT_PUBLIC_API_BASE_URL=http://localhost:4010`.

## Layout

```
src/
  app/          routes (App Router), sitemap.ts, robots.ts
  components/   layout/ (header, mega-menu, mobile drawer, footer, theme), tools/ (FileDropzone,
                ProcessingStatus, ToolSearch, ToolWorkspace, ToolPage, CategoryPage), home/, pricing/, ui/
  hooks/        (reserved for shared client hooks)
  lib/          catalog loader, config (site, categories, pricing, retention), API client, SEO, security headers
  services/     catalog queries used by pages
  types/        catalog types derived from the generated OpenAPI types
  proxy.ts      returns a real 404 for unknown /tools/{slug}
tests/unit      Vitest tests      tests/e2e  Playwright smoke tests
```

### Single sources of truth

- **Tool catalog**: `../shared/tool-catalog.json` (owned by the backend). Imported at build time via the
  `@shared/*` alias; `lib/catalog.ts` checks the invariants the UI needs and fails the build if they break, and
  `tests/unit/catalog.test.ts` validates the file against `shared/tool-catalog.schema.json` with Ajv (draft 2020-12).
  Catalog types come from the generated OpenAPI types, so nothing is hand-mirrored.
- **Brand name**: `siteConfig.name` in `src/lib/config/site.ts` (currently a neutral placeholder).
- **Pricing**: `src/lib/config/pricing.ts`, **display only**. The server is the source of truth and enforces limits.
- **Retention copy**: `src/lib/config/retention.ts`, display only, mirrors docs/privacy.md and server settings.
- **Categories**: `src/lib/config/categories.ts` maps contract category ids to names, SEO slugs and copy.

## Routes

| Route | Notes |
|---|---|
| `/` | Hero, search, popular tools, categories, privacy lifecycle, why us, pricing summary, FAQ |
| `/tools` | All tools grouped by category |
| `/tools/{tool-slug}` | One static page per catalog tool (e.g. `/tools/merge-pdf`) |
| `/tools/{category-slug}` | Category pages: `organize-pdf-tools`, `optimize-pdf`, `convert-to-pdf`, `convert-from-pdf`, `edit-pdf-tools`, `pdf-security`, `image-to-text-tools`, `ai-document-tools`, `webpage-comparison` |
| `/pricing`, `/about`, `/contact`, `/security` | Content pages |
| `/privacy`, `/terms` | Clearly marked DRAFT shells pending legal review |
| `/dashboard`, `/subscription` | Stubs (`noindex`, disallowed in robots.txt) until sign-in ships |
| `/sitemap.xml`, `/robots.txt` | Generated from the catalog and category config |

**Why tools live at `/tools/{slug}`**: the contract documents tool URLs as `/tools/{slug}`
(`shared/tool-catalog.schema.json`), and a prefix keeps tool slugs from ever clashing with site pages such as
`/pricing`. Categories share the same segment with their own SEO slugs; a unit test guarantees category slugs never
equal a tool slug (several obvious names, such as `organize-pdf`, `edit-pdf` and `image-to-text`, are tool slugs,
which is why those categories use `-tools` suffixes).

## Security headers

Set for every route in `next.config.ts` (built by `src/lib/security-headers.ts`): Content-Security-Policy,
Referrer-Policy `strict-origin-when-cross-origin`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
Permissions-Policy (camera, microphone, geolocation, payment and other sensors off), COOP/CORP `same-origin`,
HSTS (production only). `poweredByHeader` is off.

CSP: `default-src 'self'`, `connect-src 'self' <API origin>`, `frame-ancestors 'none'`, `object-src 'none'`,
`base-uri 'self'`, `form-action 'self'`, `upgrade-insecure-requests` when the API is HTTPS. `script-src` keeps
`'unsafe-inline'` because pages are statically prerendered (nonces would force per-request rendering) and Next.js
and next-themes inject small inline bootstrap scripts. There are no third-party scripts, no analytics and no
user-generated HTML. Development additionally allows `'unsafe-eval'` and websockets for HMR.

## Deploying on Vercel (monorepo)

- **Root Directory**: `frontend`
- **Include files outside the root directory in the Build Step**: **enabled** (Vercel's default). The build reads
  `../shared/tool-catalog.json` (and `npm run api:types` reads `../shared/openapi.yaml`). `next.config.ts` sets
  `turbopack.root` and `outputFileTracingRoot` to the monorepo root so these imports resolve.
- **Framework preset**: Next.js. Install `npm ci`, build `npm run build` (defaults are fine).
- **Node.js version**: 24.x.
- **Environment variables**: `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_API_BASE_URL` (Production and Preview).
- Ignored build step (optional): rebuild when `frontend/` or `shared/` changes.
- Do not enable Vercel Analytics or Speed Insights (Phase 1 privacy stance: no tracking).

Self-hosting works the same way: `npm ci && npm run build && npm run start -- -p 3000` from `frontend/` with the
monorepo checked out (the `shared/` folder must be present at build time only).

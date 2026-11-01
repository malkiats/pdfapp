# Deployment outline

Status: **outline only. Phase 8 completes this** (infrastructure as code, environments, runbooks). Nothing here contains real account ids, hostnames or secrets. Placeholders are written as `<like-this>`.

Source of truth for the topology: [docs/architecture.md §5–§7](../../docs/architecture.md) and [ADR-0002](../../docs/adr/0002-temp-storage-and-cleanup.md).

## 1. Frontend: Vercel

| Setting | Value |
|---|---|
| Framework preset | Next.js |
| Root directory | `frontend/` |
| Include files outside the root directory in the build step | **Enabled**. The build reads `../shared/tool-catalog.json` (architecture.md §9, spike S6). Fallback if it misbehaves: a `prebuild` script that copies `shared/` into `frontend/`. |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Node.js version | 24.x (matches `.nvmrc`) |
| Ignored build step | Optional: skip when only `backend/` or `infrastructure/` changed |

Environment variables (Vercel project settings, per environment). Public configuration only: a `NEXT_PUBLIC_*` value is shipped to browsers, so a secret must never be placed in one (security.md §6).

| Variable | Production | Preview |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.<apex>` | staging API URL |
| `NEXT_PUBLIC_SITE_URL` | `https://<apex>` | Vercel preview URL |
| `NEXT_PUBLIC_SUPABASE_URL` (Phase 4) | `https://<project-ref>.supabase.co` | staging project |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` (Phase 4) | anon key (public by design) | staging anon key |

The frontend never proxies file bytes. Browsers upload to and download from the API directly, so the API's CORS allowlist must contain the production origin (and preview origins only in non-prod).

## 2. Backend: AWS ECS Fargate, `ap-southeast-1` (default)

One image (`backend/Dockerfile`), pushed to a private ECR repository, tagged with the git SHA (immutable tags) plus a semver release tag. Each role is its own ECS service using the same task image with a different command.

```
                   Internet
                      |
                 [ ALB (HTTPS) ]          access logs off or path-only
                      |
   public subnets ----+---------------------------------------------
                      |
   private subnets    v   (NAT egress)
     api  ------------------------> Supabase JWKS / Postgres, payment provider
     worker-web  (SSRF-guarded) --> public web, 80/443 only
     worker-ai  -------------------> Groq API only
     sweeper
                      |
   isolated subnets (NO NAT, no IGW route)
     worker-docs ---> S3 gateway endpoint, ElastiCache only

   ElastiCache Valkey (TLS + AUTH, no snapshots)   S3 <prefix>-workspaces (private)
```

| Role | ECS service | Subnet | Egress | Scaling |
|---|---|---|---|---|
| `api` | behind ALB, ≥ 2 tasks | private (NAT) | Supabase, payment provider | CPU / request count |
| `worker-docs` | no load balancer | **isolated, no NAT** | S3 VPC endpoint, Valkey | queue depth (`docs`) |
| `worker-web` | no load balancer | private (NAT) | 80/443 to the internet | queue depth (`web`) |
| `worker-ai` | no load balancer | private (NAT) | Groq only (egress proxy or SG + pinned client) | queue depth (`ai`) |
| `sweeper` | exactly 1 task | private | S3, Valkey, Postgres | fixed |

Task hardening (mirrors compose.yaml): `readonlyRootFilesystem: true`, `user: "10001:10001"`, Linux capabilities drop `ALL`, `initProcessEnabled: true` (the image also ships tini), ephemeral `tmpfs`-style volumes for `/tmp` and `/work` (Fargate: task ephemeral storage, sized per role), CPU and memory limits per service, no privileged mode, no Docker socket.

Data services:

| Piece | Service | Notes |
|---|---|---|
| Queue + job state | ElastiCache Valkey | In-VPC, TLS + AUTH token, **no snapshots / backups**, `noeviction` |
| Temp storage | S3 bucket `<prefix>-workspaces` | Private, Block Public Access on, SSE, **versioning off, no replication, excluded from AWS Backup**, lifecycle rule expiring `ws/` after 1 day, gateway VPC endpoint |
| User/billing data (Phase 4) | Supabase Postgres (Singapore) | Schema `app`, backend-only access, TLS |
| Secrets | AWS Secrets Manager | Injected as ECS task env (`secrets`), one secret set per environment |

IAM (least privilege):
- Task roles for api, workers and sweeper: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` on `arn:aws:s3:::<prefix>-workspaces` with the `ws/*` prefix only.
- Task execution role: pull from the ECR repository and read only that environment's secrets.
- CI deploy role: GitHub OIDC federation (no long-lived keys), scoped to ECR push and ECS service update for the target environment.

## 3. Release pipeline (to build in Phase 8)

1. CI (`.github/workflows/ci.yml`) green on `main`.
2. Build once, scan (Trivy), push `<registry>/doctools-backend:<git-sha>` to ECR.
3. Deploy to staging automatically. Run the smoke checks (`/health`, `/ready`).
4. Production deploy behind a manual approval (GitHub environment protection rule), using the **same image digest** that passed staging.
5. Rolling deployment with the ECS deployment circuit breaker and automatic rollback.

## 4. Open items before production

- Spike S1 (architecture.md §9): network-less subprocesses on the chosen platform. Fargate relies on subnet isolation for `worker-docs`. Fly.io is the lower-cost alternative using `bwrap --unshare-net`.
- `worker-docs` switches to the `runtime-docs-native` image target in Phase 3 (LibreOffice, Tesseract, qpdf; no Ghostscript, ADR-0004).
- Edge protection (CDN/WAF in front of `api.<apex>`) before public launch (security.md §4).
- Infrastructure as code (Terraform or CDK), per-environment state, and runbooks.

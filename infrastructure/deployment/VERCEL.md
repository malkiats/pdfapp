# Deploy to Vercel: step-by-step guide

This guide puts the whole Phase 1 app on Vercel:

| Vercel project | Folder | What it is | Example URL |
|---|---|---|---|
| **Project 1: backend** | `backend/` | FastAPI API (health, readiness, tool catalog) | `https://doctools-api.vercel.app` |
| **Project 2: frontend** | `frontend/` | Next.js website | `https://doctools.vercel.app` |

Both projects come from the **same GitHub repository**. Create the backend first, because the frontend needs its URL.

---

## 0. Before you start: what works today

The app is at **Phase 1 (foundation)**. Read this so you know what to expect after the deployment.

- **Works:** the website (home, tools list, tool pages, pricing, privacy, security), the API endpoints `/health`, `/ready`, `/api/v1/tools` and `/api/v1/tools/{slug}`.
- **Not built yet:** actual document processing. Every tool shows "Coming soon". No upload, convert or OCR feature runs yet. This is by design (see [docs/architecture.md §10](../../docs/architecture.md)).
- **Postgres is not used yet.** Accounts, plans and payments arrive in Phase 4. Until then, the app has no database code. You can create the database now (step 5) so it is ready, but the app will not read it.
- **Plan:** Vercel's free Hobby plan is for personal, non-commercial use only. This is a commercial product, so use the **Pro** plan for the real launch.

> **Important for later phases.** The document workers (LibreOffice, Tesseract, long jobs, large uploads) **cannot run on Vercel**. Vercel Functions accept a request body of at most about 4.5 MB, and they are not built for long-running workers. When Phase 2 starts, the backend API and workers must move to a container host (AWS ECS, Fly.io, Render, Railway…). The frontend can stay on Vercel. See [README.md](README.md) in this folder.

---

## 1. Things you need

1. A **GitHub** account (or GitLab or Bitbucket).
2. A **Vercel** account, signed in with that GitHub account: <https://vercel.com/signup>
3. On your Mac: `git` and `openssl` (both come with macOS).

---

## 2. Put the code on GitHub

The repository has no commits yet. Run these commands in a terminal, from the project folder:

```bash
cd ~/Documents/Repos/PythonApp

# Check that no secret or large file is about to be committed.
# You must NOT see: .env, any *.zip, node_modules, .venv
git status --short

git add .
git commit -m "Phase 1 foundation"
```

Then create an **empty private repository** on GitHub (no README, no .gitignore). Copy its URL and run:

```bash
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

> `pdfapp.zip` (280 MB) is excluded by `.gitignore`. GitHub refuses files bigger than 100 MB.

---

## 3. Create the backend project (FastAPI)

1. Go to <https://vercel.com/new>.
2. Click **Import** next to your repository.
3. Set these values:

   | Setting | Value |
   |---|---|
   | Project Name | `doctools-api` (any name) |
   | Framework Preset | **FastAPI** (pick it if Vercel does not detect it) |
   | Root Directory | click **Edit**, choose `backend` |
   | Build / Install / Output commands | leave the defaults |

4. Do **not** click Deploy yet. First open **Environment Variables** and add the values from step 3a.

### 3a. Backend environment variables

Create a random secret key in your terminal:

```bash
openssl rand -hex 32
```

Add these variables (Environment: **Production**):

| Name | Value | Notes |
|---|---|---|
| `APP_ENV` | `prod` | Turns on production safety checks. |
| `APP_SECURITY__IP_HASH_KEY` | the 64-character value from `openssl` | **Secret.** Used to hash visitor IPs. Never share it. |
| `APP_CORS__ALLOWED_ORIGINS` | `https://doctools.vercel.app` | The frontend URL. You do not know it yet, so put this placeholder in now and fix it in step 6. Use `https`, no slash at the end. |

`APP_REDIS__URL` is also **required** when `APP_ENV=prod`. You add Redis in step 4. Until then the first deployment fails with `missing required settings for prod: APP_REDIS__URL`. That is expected.

For **Preview** deployments (other branches), add `APP_ENV` = `staging` instead. Staging does not need Redis.

### 3b. Settings already handled in code

You do **not** need to set these. `backend/server.py` sets them for Vercel:

- writable folders under `/tmp` (Vercel only allows writing there)
- the tool catalog path (copied from `shared/` at build time by `scripts/vercel_build.py`)
- the real visitor IP from Vercel's `X-Forwarded-For` header (for rate limiting)
- `APP_REDIS__URL` from `REDIS_URL` / `KV_URL`, if a Marketplace Redis is connected

Click **Deploy**.

---

## 4. Add Redis to the backend (required in production)

Redis stores the rate-limit counters, which every server instance shares.

1. Open the **backend** project → **Storage** tab → **Create Database**.
2. Choose **Upstash for Redis** (or another Redis from the Marketplace). Pick the free plan and the region closest to your users (for example Singapore).
3. On the **Connect Project** screen, choose the backend project and tick **Production** (Preview is optional).
4. Vercel adds variables such as `REDIS_URL` and `KV_URL` to the project. The backend picks them up automatically.
   - If neither variable appears, open the database page in Vercel, copy the connection string (starts with `rediss://`), and add it yourself as `APP_REDIS__URL`.
5. Go to **Deployments** → open the latest one → **⋯** → **Redeploy**.

### Check the backend

Open these URLs in a browser (use your own backend URL):

| URL | Expected result |
|---|---|
| `https://doctools-api.vercel.app/health` | `{"status":"ok"}` |
| `https://doctools-api.vercel.app/ready` | `{"status":"ready","checks":{"redis":"ok","storage":"ok"}}` |
| `https://doctools-api.vercel.app/api/v1/tools` | A JSON list of tools |

If something fails: backend project → **Logs**. The error says which setting is missing or wrong.

---

## 5. (Optional) Create the Postgres database

Skip this if you prefer. The current code does **not** use a database. Create it now only to have it ready for Phase 4.

1. Backend project → **Storage** → **Create Database**.
2. Choose **Neon** (Serverless Postgres). Vercel's own "Vercel Postgres" is closed; Neon replaced it.
3. Pick the free plan and the same region as Redis.
4. Connect it to the **backend** project only (never to the frontend). Tick Production, and Preview if you want a separate preview branch database.
5. Vercel adds `DATABASE_URL`, `POSTGRES_URL` and related variables. Leave them as they are.

**Rules for when the database gets used (Phase 4):**

- Only the backend talks to Postgres. Never put a database URL in a `NEXT_PUBLIC_*` variable.
- Never store file names, document text, OCR text, AI prompts or URLs in the database ([docs/privacy.md](../../docs/privacy.md)).

---

## 6. Create the frontend project (Next.js)

1. Go to <https://vercel.com/new> again and **Import the same repository**.
2. Set:

   | Setting | Value |
   |---|---|
   | Project Name | `doctools` (any name) |
   | Framework Preset | **Next.js** |
   | Root Directory | `frontend` |
   | Install Command | `npm ci` |
   | Build Command | `npm run build` (default) |

3. **Environment Variables** (Production and Preview):

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | your backend URL, e.g. `https://doctools-api.vercel.app` (no slash at the end) |
   | `NEXT_PUBLIC_SITE_URL` | Production only: your site URL, e.g. `https://doctools.vercel.app`. You can leave it out: Vercel then uses the production domain automatically. |

   Values that start with `NEXT_PUBLIC_` are visible to everyone in the browser. **Never put a password or key in them.**

4. Click **Deploy**.
5. After the deployment, open **Settings**:
   - **General → Node.js Version**: `24.x`.
   - **Build and Deployment → Root Directory**: make sure **"Include files outside the root directory in the Build Step"** is **ON**. The build reads `../shared/tool-catalog.json`.
   - If you changed either setting, redeploy.

---

## 7. Connect the two projects

1. Copy the real frontend address from the frontend project's main page (for example `https://doctools.vercel.app`, or your own domain).
2. Backend project → **Settings → Environment Variables** → edit `APP_CORS__ALLOWED_ORIGINS`:
   - one site: `https://doctools.vercel.app`
   - several sites: separate them with commas, e.g. `https://doctools.vercel.app,https://www.yourdomain.com`
3. Redeploy the backend.

---

## 8. Final check

1. Open the frontend URL. The home page, `/tools`, a tool page such as `/tools/merge-pdf`, and `/pricing` should all load.
2. In the browser, press **F12** → **Console**. There should be no red CSP or CORS errors.
3. Open `https://<backend>/ready` again. It should still say `ready`.

---

## 9. Custom domain (optional)

1. Frontend project → **Settings → Domains** → add `yourdomain.com` and `www.yourdomain.com`. Follow the DNS steps that Vercel shows.
2. Backend project → **Settings → Domains** → add `api.yourdomain.com`.
3. Update the variables, then redeploy **both** projects:
   - frontend: `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com`, `NEXT_PUBLIC_SITE_URL=https://yourdomain.com`
   - backend: `APP_CORS__ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`

The frontend must be **rebuilt** after you change a `NEXT_PUBLIC_*` value, because the build bakes those values into the site.

---

## 10. Common problems

| Problem | Fix |
|---|---|
| Backend log: `missing required settings for prod: APP_REDIS__URL` | Do step 4, then redeploy. |
| Backend log: `APP_SECURITY__IP_HASH_KEY must be at least 32 characters` | Use the full `openssl rand -hex 32` output. |
| Backend log: `prod CORS origins must use https` | Every value in `APP_CORS__ALLOWED_ORIGINS` must start with `https://`. |
| Backend log mentions `tool-catalog.json` not found | Backend → Settings → Root Directory → turn ON "Include files outside the root directory", then redeploy. |
| Frontend build: `NEXT_PUBLIC_API_BASE_URL must be set for production builds` | Add the variable (step 6) and redeploy. |
| Frontend build cannot find `../shared/tool-catalog.json` | Turn ON "Include files outside the root directory in the Build Step". |
| Browser console: CORS error | The frontend address is missing from `APP_CORS__ALLOWED_ORIGINS`, or it has a trailing slash. Fix it and redeploy the backend. |
| `/ready` shows `"redis":"failed"` | The Redis URL is wrong, or the Redis database is paused or deleted. Check the Storage tab. |

---

## 11. Every later update

Push to `main`. Vercel redeploys both projects automatically. Other branches get their own preview URLs.

```bash
git add .
git commit -m "Describe the change"
git push
```

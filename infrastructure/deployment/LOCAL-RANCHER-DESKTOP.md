# Run locally on Rancher Desktop (Docker): step-by-step guide

This runs the full stack on your Mac with Docker containers, through Rancher Desktop:

| Service | What it does | Address |
|---|---|---|
| `api` | FastAPI backend | <http://localhost:8000> |
| `valkey` | Redis-compatible queue and rate-limit store | internal only |
| `worker-docs`, `worker-web`, `worker-ai` | Job workers (no processing yet in Phase 1) | internal only |
| `sweeper` | Deletes expired temp files | internal only |
| `frontend` (optional) | Next.js dev server | <http://localhost:3000> |
| `postgres` (optional) | Database for Phase 4 (not used yet) | internal only |
| `mock` (optional) | Fake API made from `shared/openapi.yaml` | <http://localhost:4010> |

---

## 1. Set up Rancher Desktop (one time)

1. Install Rancher Desktop from <https://rancherdesktop.io> and open it.
2. Open **Preferences** (⌘ ,) and set:

   | Section | Setting | Value |
   |---|---|---|
   | **Container Engine** | Engine | **dockerd (moby)**. Do not choose containerd: `docker compose` needs moby. |
   | **Virtual Machine → Hardware** | Memory | **6 GB** or more (8 GB if you also run the frontend in Docker) |
   | | CPUs | **4** |
   | **Virtual Machine → Emulation** (macOS) | Virtual Machine Type | **VZ** (Apple Virtualization) |
   | **Virtual Machine → Volumes** (macOS) | Mount Type | **virtiofs** (faster file sharing) |
   | **Kubernetes** | Enable Kubernetes | **Off** (not needed, saves memory) |

3. Click **Apply**. Wait until the status at the bottom of the window shows that everything is running.

4. Check it in a terminal:

   ```bash
   docker context use rancher-desktop
   docker version          # must show a "Server:" section
   docker compose version  # must be v2.24 or newer
   ```

   If you see `Cannot connect to the Docker daemon`, Rancher Desktop is still starting or is not running. Wait and try again.

---

## 2. Install the developer tools (one time)

```bash
# Homebrew: https://brew.sh
brew install uv node@24
```

- `uv` installs Python 3.12 and the backend packages.
- `node` 24 and `npm` are for the frontend.
- `make` and `openssl` come with macOS.

---

## 3. First-time setup

```bash
cd ~/Documents/Repos/PythonApp
make setup
```

This does three things:

1. Creates `.env` from `.env.example` and fills every `__GENERATE__` with a random secret. Never commit `.env`; it is already in `.gitignore`.
2. Installs the backend packages (`backend/.venv`).
3. Installs the frontend packages (`frontend/node_modules`).

---

## 4. Start the backend stack

```bash
make dev
```

The first run downloads images and builds the backend image. That takes a few minutes. The command waits until every service is healthy.

Check it:

```bash
curl http://localhost:8000/health        # {"status":"ok"}
curl http://localhost:8000/ready         # {"status":"ready","checks":{"redis":"ok","storage":"ok"}}
curl http://localhost:8000/api/v1/tools  # list of tools (JSON)
make ps                                  # every service "healthy" or "running"
```

---

## 5. Start the website

Pick **one** of these options.

**Option A: on your Mac (fastest, recommended)**

```bash
cd frontend
cp .env.example .env.local   # first time only
npm run dev
```

**Option B: inside Docker as well**

```bash
make dev-all   # backend stack + frontend + postgres + mock API
```

The first start runs `npm ci` inside the container and can take a few minutes. Follow it with `make logs SERVICE=frontend`.

Open <http://localhost:3000>.

---

## 6. Test a production-like build of the website (optional)

This is the same build that Vercel runs:

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 NEXT_PUBLIC_SITE_URL=http://localhost:3000 npm run build
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 NEXT_PUBLIC_SITE_URL=http://localhost:3000 npm start
```

---

## 7. Run the tests

```bash
make lint      # code style and type checks (backend + frontend + contract)
make test      # backend pytest + frontend vitest
make test-e2e  # browser smoke tests (downloads Chromium the first time)
```

---

## 8. Everyday commands

| Command | What it does |
|---|---|
| `make dev` | Start or rebuild the backend stack |
| `make dev-all` | Backend stack + frontend + postgres + mock |
| `make ps` | Show the status of each service |
| `make logs` | Follow all logs (`make logs SERVICE=api` for one service) |
| `make down` | Stop everything (Postgres data is kept) |
| `make clean` | Stop and delete temp files and caches |
| `make clean-all` | Also delete the Postgres data and all volumes |
| `make help` | List every command |

Optional Postgres only:

```bash
docker compose --profile db up -d postgres
docker compose exec postgres psql -U doctools -d doctools   # opens a SQL prompt
```

---

## 9. Without `make` (plain Docker commands)

```bash
make .env                                # only creates .env with random secrets
docker compose up --build --detach --wait
docker compose --profile frontend up --detach --wait frontend   # optional website
docker compose down
```

---

## 10. Common problems

| Problem | Fix |
|---|---|
| `Cannot connect to the Docker daemon at unix://…/.rd/docker.sock` | Start Rancher Desktop and wait until it is ready. Then run `docker context use rancher-desktop`. |
| `.env.example is missing` | Pull the latest code; the file must be at the project root. |
| `port is already allocated` for 8000 or 3000 | Something else uses the port. Stop it, or set `API_PORT=8001` / `FRONTEND_PORT=3001` in `.env`. If you change `API_PORT`, also change `NEXT_PUBLIC_API_BASE_URL`. |
| A container restarts again and again, or `make dev` times out | Run `make logs SERVICE=<name>`. Often Rancher Desktop does not have enough memory: raise it to 6–8 GB in Preferences. |
| Build error about `additional_contexts` or BuildKit | Update Rancher Desktop. Its bundled Compose must be v2.24 or newer. |
| Frontend in Docker is very slow or does not hot-reload | Use Option A (run the frontend on your Mac), or set Mount Type to **virtiofs**. |
| `mock` will not start | It downloads Prism from npm on the first start, so it needs internet. Retry `make mock`. |
| You want a completely fresh start | `make clean-all`, then `make dev`. |

# Deploy (free) — Vercel + Render + Supabase

Three free services. Order matters: **Supabase → Render → Vercel → wire CORS**.

## 0. Push your code to GitHub
Both Vercel and Render deploy from a GitHub repo.
```
git add render.yaml frontend/vercel.json DEPLOY.md
git commit -m "Add deploy configs"
git push
```

## 1. Supabase (DB + Auth)  —  https://supabase.com
- You likely already have a project (used in dev). Reuse it.
- Grab from **Project Settings → API**:
  - Project URL            → `SUPABASE_URL` (and `VITE_SUPABASE_URL`)
  - `anon` public key      → `VITE_SUPABASE_ANON_KEY`
  - `service_role` key     → `SUPABASE_SERVICE_KEY`  (SECRET — backend only)
  - JWT secret (Settings → API → JWT) → `SUPABASE_JWT_SECRET`
- Make sure the `documents` and `exports` storage buckets exist.

## 2. Render (backend / FastAPI)  —  https://render.com
- New → **Blueprint** → pick this repo. It reads `render.yaml`.
- When prompted, fill the secret env vars:
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
  - `OPENROUTER_API_KEY`  (from https://openrouter.ai/keys — free)
  - `SUPER_ADMIN_EMAILS`  (your email)
  - `ALLOWED_ORIGINS` → leave as `http://localhost:5173` for now, fix in step 4
  - `OPENROUTER_REFERER` → same as ALLOWED_ORIGINS
- Deploy. Note the URL, e.g. `https://exam-generator-api.onrender.com`.
- Test: open `<that url>/health` → should return `{"status":"ok"}`.

## 3. Vercel (frontend / Vite)  —  https://vercel.com
- New Project → import this repo.
- **Set Root Directory = `frontend`** (important — repo root is not the app).
- Add Environment Variables:
  - `VITE_API_URL`           = your Render URL (no trailing slash)
  - `VITE_SUPABASE_URL`      = Supabase project URL
  - `VITE_SUPABASE_ANON_KEY` = Supabase anon key
- Deploy. Note the URL, e.g. `https://your-app.vercel.app`.

## 4. Wire CORS (the step everyone forgets)
- Back in Render → the service → Environment:
  - `ALLOWED_ORIGINS` = `https://your-app.vercel.app`
  - `OPENROUTER_REFERER` = `https://your-app.vercel.app`
- Save → Render redeploys. Done.

## Demo-day notes
- Render free **sleeps after ~15 min idle**; first hit takes ~30–50s to wake.
  Before your demo, open `<render-url>/health` once to warm it up.
- OpenRouter `:free` models are rate-limited — fine for a live demo, not a crowd.
- Supabase free projects pause after ~1 week idle (one click to resume).

## Region, monitoring & scaling (production)
- **Region:** `render.yaml` pins the API to `frankfurt` (EU) — close to the
  primary French/Arabic audience and keeps data in the EU for GDPR. Keep the
  Supabase project in the same region to minimise DB round-trip latency. Change
  the `region` field if your audience is elsewhere.
- **Monitoring/alerting:** the app logs structured warnings/errors at
  `LOG_LEVEL` (default `INFO`). In the Render dashboard, add a **Log Stream**
  drain and configure **Health Check** alerts on `/health`. Set up alerts on
  repeated 5xx / rate-limit (429) spikes. *(Needs to be enabled in the
  dashboard — not expressible in `render.yaml`.)*
- **CDN / replication (evaluate):** the frontend is already served from Vercel's
  global CDN. For the API, a single free instance is the current bottleneck;
  before going wide, move exam generation to a durable queue + worker (see the
  in-process job runner in `app/services/jobs.py`) and add a Supabase read
  replica for distant users. *(Needs infra provisioning and load testing to
  confirm.)*
- **Rate limiting:** the API applies per-client limits in-process
  (`app/rate_limit.py`). This is per-instance; if you scale to multiple
  instances, back it with Render Key Value (Redis) so limits are shared.

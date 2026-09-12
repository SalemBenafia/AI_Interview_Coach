# Setup Guide

From a clean clone to a working live voice interview, then the local-development
workflow, testing, troubleshooting and production hardening.

For what the system *is* and how it's put together, see [README.md](README.md).

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Configure environment files](#2-configure-environment-files)
3. [Get a Groq API key](#3-get-a-groq-api-key)
4. [Start the stack](#4-start-the-stack)
5. [Download the models](#5-download-the-models)
6. [Migrate and seed the database](#6-migrate-and-seed-the-database)
7. [Verify everything is up](#7-verify-everything-is-up)
8. [Run your first interview](#8-run-your-first-interview)
9. [Admin AI Studio tour](#9-admin-ai-studio-tour)
10. [Local development workflow](#10-local-development-workflow)
11. [Testing](#11-testing)
12. [Troubleshooting](#12-troubleshooting)
13. [Production checklist](#13-production-checklist)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker + Compose v2 | ≥ 24.0 | the whole stack runs in containers |
| Node.js | ≥ 20 | only for running the frontend outside Docker |
| Python | ≥ 3.11 | only for running backend processes outside Docker |
| Groq account | free | LLM reasoning — see [step 3](#3-get-a-groq-api-key) |
| Disk | ~6 GB | images, model caches, the Piper voice |
| RAM | 8 GB | compose limits are tuned for 8 GB / 2 cores |

No GPU is required. Whisper and the sentiment model run on CPU (int8), and LLM
inference is remote.

## 2. Configure environment files

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# or: make env-copy   (copies only what doesn't already exist)
```

Which file is read when:

| File | Read by |
|---|---|
| `.env` (root) | `docker-compose.yml` — both for `${VAR}` substitution and as `env_file` for the backend, celery, voice-agent and frontend containers. **This is the one that matters for Docker runs.** |
| `backend/.env` | only when you run a backend process directly on the host (`uvicorn`, `celery`, `alembic`, `seed.py`) from inside `backend/` |
| `frontend/.env` | only when you run `npm run dev` on the host; in Docker these three values come from `docker-compose.yml` |

Add your Groq key to the root `.env` (the committed example doesn't include it
yet — see the note below):

```bash
GROQ_API_KEY=gsk_your_key_here
```

Then change every secret before the app leaves your machine:

```
SECRET_KEY            32+ random characters
JWT_SECRET_KEY        32+ random characters, different from SECRET_KEY
POSTGRES_PASSWORD     anything but the committed default
MINIO_ROOT_PASSWORD   anything but the committed default
LIVEKIT_API_KEY       never ship "devkey"
LIVEKIT_API_SECRET    32+ characters
```

> **Note — stale keys in the committed examples.** `.env.example` and
> `backend/.env.example` still list `OPENROUTER_*`, `QDRANT_*` and
> `EMBEDDING_*` variables from an earlier architecture. Nothing reads them
> (`Settings` is configured with `extra="ignore"`), and neither a vector
> database nor an embedding service exists in this repo. Ignore them, or
> delete them from your copies. The variable the LLM layer actually reads is
> `GROQ_API_KEY`.

Useful non-secret settings, all in root `.env`:

| Variable | Default | Effect |
|---|---|---|
| `WHISPER_MODEL` | `base` | `tiny`/`base`/`small` for speed, `large-v3` for accuracy (much slower on CPU) |
| `WHISPER_COMPUTE_TYPE` | `int8` | CPU quantization |
| `PIPER_VOICE` | `en_US-amy-medium` | must match a downloaded voice file |

LLM model selection lives in
[settings.py](backend/app/core/settings.py#L137) — `GROQ_MODEL` (default
`allam-2-7b`) and `GROQ_FALLBACK_MODEL` (default `llama-3.1-8b-instant`). Set
either in root `.env` to override.

## 3. Get a Groq API key

1. Sign up at <https://console.groq.com> — no credit card required.
2. Create a key under **API Keys** (it starts with `gsk_`).
3. Put it in root `.env` as `GROQ_API_KEY`.
4. If the stack is already running, restart the processes that call the LLM:
   ```bash
   docker compose up -d --force-recreate backend celery_worker voice-agent
   ```

The free developer tier is rate-limited per model (requests/minute,
requests/day and tokens/minute — see <https://console.groq.com/docs/rate-limits>).
[llm_client.py](backend/app/modules/agents/llm_client.py) retries transient
failures and falls back to `GROQ_FALLBACK_MODEL`; if both are exhausted it
raises `AgentServiceError` rather than inventing output.

Verify the key works:

```bash
docker compose exec backend python -c "
import os, httpx
r = httpx.get('https://api.groq.com/openai/v1/models',
              headers={'Authorization': 'Bearer ' + os.environ['GROQ_API_KEY']},
              timeout=10)
print(r.status_code, len(r.json().get('data', [])), 'models')"
```

`200` and a non-zero model count means you're set. (The `make check-openrouter`
target is left over from the previous provider and checks the wrong variable.)

## 4. Start the stack

```bash
make docker-up          # docker compose up -d
```

First run builds four images and pulls six more — expect 5–15 minutes.
What comes up:

1. `postgres`, `redis`, `minio`, `mailhog` — stateful infrastructure
2. `coturn`, `livekit` — WebRTC
3. `stt-service`, `tts-service`, `signal-service` — the AI microservices
4. `backend`, `celery_worker`, `celery_beat`, `voice-agent` — the application
5. `frontend`, `playwright`

There is no LLM container (Groq is remote) and no vector-database container.

## 5. Download the models

### Piper voice — required, one-time

The TTS service refuses to synthesize without a voice file, and voice files are
gitignored. Download inside the container (no host Python dependency):

```bash
docker compose exec tts-service python -m piper.download_voices \
  en_US-amy-medium --download-dir /app/voices
```

Or on the host, if `piper-tts` is installed there:

```bash
make download-voice
```

Either way the files land in `services/tts-service/voices/`, which is
bind-mounted into the container. To use a different voice, download it and set
`PIPER_VOICE` in root `.env`.

### Whisper and the sentiment model — automatic

`faster-whisper` downloads `WHISPER_MODEL` on the first transcription request
and caches it in the `whisper_cache` volume. The emotion classifier
(`j-hartmann/emotion-english-distilroberta-base`) does the same into
`signal_cache`. The first request after a cold start is therefore slow; later
ones are not.

## 6. Migrate and seed the database

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
```

Seeding creates:

- a super admin — `admin@interview-coach.ai` / `Admin@123456`
- a demo candidate — `demo@interview-coach.ai` / `Demo@123456`
- a sample target role with background fields for the demo candidate
- difficulty rules for junior / mid / senior
- the five default agent templates
- one published, default-marked flow for each of the four interview modes

The `make db-migrate` / `make db-seed` targets do the same thing from the host
and require a local virtualenv plus a `backend/.env` whose `DATABASE_URL` points
at `localhost:5433` (Postgres is published on **5433**, not 5432). The
`docker compose exec` form above works regardless.

## 7. Verify everything is up

```bash
docker compose ps                       # every service "running"
curl http://localhost:8000/health       # {"status":"ok",...}
curl http://localhost:9002/health       # STT  (container port 9001 → host 9002)
curl http://localhost:5002/health       # TTS  (reports default_voice)
curl http://localhost:8089/health       # sentiment
curl http://localhost:7880              # LiveKit (no /health route — any reply is fine)
```

| URL | What |
|---|---|
| <http://localhost:3000> | the app |
| <http://localhost:8000/api/docs> | OpenAPI docs (only when `DEBUG=true`) |
| <http://localhost:8025> | MailHog — every dev email lands here |
| <http://localhost:9001> | MinIO console (`minioadmin` / your `MINIO_ROOT_PASSWORD`) |

## 8. Run your first interview

1. Open <http://localhost:3000> and sign in as `demo@interview-coach.ai` /
   `Demo@123456`. There is one login form for both candidates and admins — the
   backend resolves which you are from the credentials.
2. Go to **Target Roles**. Use the seeded role or create one, add background
   fields (experience, skills, projects), then click **Analyze**.
3. Wait for the role's status to become **ready** — a Celery task is extracting
   structured knowledge entries via the LLM. Watch it with
   `docker compose logs -f celery_worker`.
4. Go to **Practice**, pick that target role, a mode and a difficulty, and start
   the interview.
5. Allow microphone access when the browser asks.
6. The AI's opening question should be spoken within a couple of seconds,
   grounded in the background you entered. Live captions appear alongside it.
7. Answer out loud. You can interrupt the AI mid-sentence — barge-in is handled
   by LiveKit's turn detection.
8. End the interview (or let it end itself). A feedback report is generated in
   the background and appears under **History**.

Silence at step 6 is almost always a missing Piper voice or a voice-agent worker
that never joined the room — see [Troubleshooting](#12-troubleshooting).

## 9. Admin AI Studio tour

Sign in at the same `/login` page with `admin@interview-coach.ai` /
`Admin@123456`. Admins control AI behaviour, never candidate content.

- **Agents** — edit the Interviewer/Evaluator/Feedback/Coach prompts and model
  settings, the Evaluator's rubric weights, and the Router's decision rules (the
  Router is a deterministic rule engine, so those rules are data, not a prompt).
  Published agents are immutable: clone to a new draft, edit, publish.
  `POST /admin/agents/{id}/test/` runs one agent for real against sample input,
  persisting nothing.
- **Flows** — the React Flow editor over `InterviewFlow.graph_json`. Publishing
  runs a validation gate that guarantees the graph compiles; **set-default**
  makes it the flow every interview in that mode uses. One default per mode.
  Node agent assignments come from a dropdown of real agent keys.
- **Content** — difficulty scaling rules only.
- **Users** — read-only inspection of any candidate's profile, target roles,
  extracted knowledge and sessions, plus suspend/activate.
- **Analytics** — KPIs, per-agent performance, trends, token usage, sentiment
  distribution.
- **Monitoring** — live sessions, an observe-token to watch one, service health,
  recent errors.
- **Security** — admin accounts, roles, audit log.

Admin sub-roles gate these: `super_admin` (everything), `platform_admin` (users,
monitoring, security), `ai_manager` (agents and prompts), `flow_designer` (flows
only), `support` (read-only).

## 10. Local development workflow

Both the backend and frontend are bind-mounted into their containers with hot
reload, so most work needs no restart. Rebuild only when dependencies change:

```bash
docker compose build backend && docker compose up -d backend celery_worker voice-agent
```

Running pieces on the host instead (useful for a debugger):

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make dev-backend        # uvicorn --reload
make dev-celery
make dev-voice-agent    # python -m app.voice_worker.worker dev

cd frontend && npm install && make dev-frontend
```

Host-run backend processes read `backend/.env`; point its `DATABASE_URL`,
`REDIS_URL` and service URLs at `localhost` with the published ports
(Postgres `5433`, STT `9002`, TTS `5002`, signals `8089`, LiveKit `7880`).

Schema changes:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

Code quality — `make lint`, `make format`, `make type-check`, `make ci`
(backend: ruff; frontend: Biome + `tsc --noEmit`).

Starting over:

```bash
make db-reset          # drop, recreate, migrate, seed — needs a host virtualenv,
                       # since its migrate/seed steps run outside Docker
docker compose down -v # also wipes volumes: DB, MinIO, model caches
```

## 11. Testing

**Backend**

```bash
docker compose exec backend pytest -v
# or on the host: cd backend && pytest -v
```

Covers flow compilation, publish-time flow validation, stale-session sweeps and
LiveKit webhook handling.

**End-to-end (Playwright)**

Requires the stack to be up and seeded.

```bash
make test-e2e                                            # whole suite
docker compose exec playwright npx playwright test e2e/candidate
docker compose exec playwright npx playwright test e2e/admin/flows-crud.spec.ts
```

The specs authenticate through real HttpOnly cookies, use fake media devices for
the microphone, and drive interviews through the dev text-turn endpoint — which
bypasses the audio transport but not the agent logic, so **every run makes real
Groq calls** and can trip free-tier rate limits. The 10-minute per-test timeout
is deliberate.

To watch a run in a browser:

```bash
docker compose exec playwright bash e2e/start-vnc.sh
docker compose exec -e HEADED=1 playwright npx playwright test e2e/candidate
# then open http://localhost:6080/vnc.html
```

`start-vnc.sh` installs its tools into the running container, so re-run it after
the container is recreated. The HTML report lands in `frontend/playwright-report/`.

## 12. Troubleshooting

### The AI never speaks

Check in order:

1. `docker compose logs voice-agent` — did the worker join? Look for
   `voice_worker_joining_room` with room `interview-<session-id>`.
2. `curl http://localhost:5002/health` — the TTS service answers even without a
   voice file, so also confirm `services/tts-service/voices/` actually contains
   `en_US-amy-medium.onnx`. Without it `/synthesize` returns **503** and the
   worker logs a failed TTS call. Fix: [step 5](#5-download-the-models).
3. `curl http://localhost:9002/health` — STT (note: **9002**, not 9001; 9001 is
   the MinIO console).
4. `docker compose logs backend | grep -i groq` — a missing or rate-limited key
   means the engine raises instead of speaking.
5. Browser console — LiveKit connection errors point at WebRTC/TURN, below.

### "password cannot be longer than 72 bytes" on login or seed

A real incompatibility between `passlib==1.7.4` and `bcrypt>=4.1`.
`backend/requirements.txt` pins `bcrypt==4.0.1` to avoid it. If you changed that
pin, revert it — or move to a newer passlib and re-test `hash_password` /
`verify_password` first.

### `409 NO_FLOW_CONFIGURED` when starting an interview

No published, default flow exists for that mode. Run the seed, or in the admin
AI Studio publish a flow and click **set-default** for the mode you're using.

### A target role stays "analyzing" / reports stay pending

Both are Celery work:

```bash
docker compose logs -f celery_worker
```

Common causes: `GROQ_API_KEY` missing or rate-limited in the worker (it's a
separate container — recreate it after editing `.env`), or `CELERY_BROKER_URL` /
`CELERY_RESULT_BACKEND` pointing at the wrong Redis database index (broker is
db1, results db2).

### WebRTC works on localhost but not from another machine

`infra/livekit/livekit.yaml` and `infra/coturn/turnserver.conf` are configured
for single-host development. For a real deployment:

1. Set `rtc.use_external_ip: true` in `livekit.yaml`.
2. Set `external-ip=<public-ip>` in `turnserver.conf`.
3. Point DNS at that IP and put LiveKit and coturn behind real TLS.
4. Update `NEXT_PUBLIC_LIVEKIT_URL` and `TURN_URL` accordingly.

### LLM calls are slow or return 429

Free-tier Groq is rate-limited per model. A 429 triggers the automatic fallback
to `GROQ_FALLBACK_MODEL`, then a typed `AgentServiceError` if both are
exhausted — grep `docker compose logs backend` for the LLM call/fallback log
lines. Options: wait out the window, switch `GROQ_MODEL` to a less contended
model, or move to a paid tier. Nothing about that is a code change.

### Containers exit with code 137

An OOM kill. The memory limits in `docker-compose.yml` are deliberate and
annotated with the failures that produced them (`tts-service` at 256 MB crashed
mid-interview; `stt-service` at 320 MB died during transcription). Raise the
limit for the affected service rather than lowering others, and check the host
actually has the RAM.

### `signal-service` build downloads gigabytes of `nvidia_*` packages

pip is resolving the CUDA build of `torch`, which this CPU-only service never
uses. `services/signal-service/requirements.txt` already pins
`torch==2.3.1+cpu` against PyTorch's CPU wheel index. If you still see it:

1. Confirm the pin: `grep cpu services/signal-service/requirements.txt`.
2. Rebuild clean: `docker compose build --no-cache signal-service`.
3. If that exact wheel no longer resolves, relax `torch==2.3.1+cpu` to plain
   `torch` while keeping the `--extra-index-url` line.

### `npm run build` warns "'Room' is not exported from 'livekit-client'"

A harmless webpack static-analysis warning — `livekit-client`'s CommonJS entry
is a UMD bundle whose named exports webpack can't verify statically. The export
exists at runtime and the app works. Safe to ignore.

### Port already in use

The published ports are listed in [README.md](README.md#services-and-ports).
The usual collisions are 5433 (a second Postgres), 3000 and 9000/9001. Change
the host side of the mapping in `docker-compose.yml`.

## 13. Production checklist

- [ ] Real `SECRET_KEY`, `JWT_SECRET_KEY`, `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`,
      `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`
- [ ] Remove the hardcoded `GROQ_API_KEY` default in
      [settings.py](backend/app/core/settings.py#L143) and supply the key
      from the environment or a secret manager; rotate that key if the repo was
      ever shared
- [ ] `DEBUG=false` (disables `/api/docs` and unmounts the dev text-turn endpoint)
      and `APP_ENV=production`
- [ ] `COOKIE_SECURE=true`, HTTPS end to end, `BACKEND_CORS_ORIGINS` set to real
      origins
- [ ] LiveKit and coturn on a real public IP/domain with TLS
- [ ] Real SMTP instead of MailHog
- [ ] Paid LLM tier — free-tier rate limits will not survive concurrent interviews
- [ ] Backups for Postgres and MinIO
- [ ] Frontend built from the Dockerfile's `runner` target, not `dev`
- [ ] Raised container memory limits and a GPU-backed Whisper deployment if you
      need the 2 s voice-latency target under load

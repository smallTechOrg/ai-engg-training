# 16.2 · Docker Compose: API, vector store, Redis, worker

**Module:** [16 · Containers and deployment](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat (script 2 only; scripts 1 and 3 call no model) · **Packages:** `apps` extra (FastAPI) · **Services:** `REDIS_URL` (script 3 only); `DOCKER` is needed only to start the stack yourself

> **Honest note:** Docker is not installed on the machine this lesson was written on. The compose file, Dockerfile and app code are checked by structure tests and by scripts 1 and 2, but the stack was **not started** by the author. Where a section needs Docker or Redis you will see the real "service missing" message from here, plus a description of what you should see when it runs.

## What you will learn

- What Docker Compose adds to lesson 16.1: one file that describes **several containers** and how they connect.
- How services find each other (service names as DNS names) and why `localhost` is wrong between containers.
- `depends_on` with healthchecks: **start order** versus **readiness**.
- Why the API **queues** slow model work and a **worker** does it, and what Redis does in between.
- Named **volumes** for state, one image used for two roles (API and worker), and a worker healthcheck.

## The idea

**What is new since 16.1:** there you built one image and ran one container. A real assistant has several moving parts, so now one `docker-compose.yml` starts four services together and wires them up.

```mermaid
flowchart LR
    U["caller / curl"] -->|"POST /tickets -> 202"| A["api<br/>FastAPI"]
    A -->|"LPUSH job"| R[("redis<br/>queue + results")]
    W["worker<br/>same image, other command"] -->|"BRPOP job"| R
    W -->|"chat completion"| M["model endpoint<br/>(LLM_BASE_URL)"]
    W -->|"SET result"| R
    A -->|"GET result"| R
    A -.->|"ready check"| C[("chroma<br/>vector store")]
    R --- V1[/"volume redis-data"/]
    C --- V2[/"volume chroma-data"/]
```

**Services and the private network.** Compose creates one network for the stack and gives every service a DNS name equal to its service name. The API reaches Redis at `redis://redis:6379/0`; `redis` is the service name. From inside a container `localhost` is that container, so `redis://localhost:6379` would fail. Only ports listed under `ports:` are reachable from your computer, and we bind them to `127.0.0.1` so the stack is not exposed to your network. Redis has no published port at all: only containers in the stack can talk to it.

**One image, two roles.** The API and the worker are the same code with different start commands (`uvicorn app.api:app` and `python -m app.worker`). One build, one image tag, and the two cannot drift apart.

**`depends_on` and health.** `depends_on` makes Compose start Redis before the API. By default it only waits until the container *exists*. `condition: service_healthy` waits until the Redis healthcheck (`redis-cli ping`) passes. Even then an app should retry its connections: a dependency can restart later. That is why the API also has `/health/ready`, which checks Redis and Chroma.

**State and volumes.** Containers are disposable; their filesystem disappears with them. Redis (with `--appendonly yes`) and Chroma write to `/data`, which is a **named volume**, so `docker compose down` keeps the queue and the vectors and only `docker compose down -v` deletes them. The API and the worker keep nothing on disk.

**Why a queue.** A model call takes seconds. If the API waits for it, slow replies hold connections open, a restart loses work in flight, and a burst of tickets overloads the provider. Instead the API stores the job and answers `202 Accepted`; the worker takes jobs at its own pace, retries transient errors a few times (never forever), and records `failed` for a job that keeps crashing. You scale by adding workers: `docker compose up -d --scale worker=3`.

**Worker health.** A worker has no HTTP port, so the compose file gives it its own check: the loop touches a heartbeat file every cycle and `python -m app.worker --check` fails if the file is older than 30 seconds. A worker stuck inside a call shows as `unhealthy`.

**The vector store.** Chroma is part of the stack so the assistant can retrieve knowledge-base articles (module 04). In this lesson the API only checks that it is alive; answers are not retrieved from it yet.

## Scripts

### 1. `01_compose_file_tour.py`: read the compose file like Compose does

```
./run 16.2/1
```

Parses the shipped `docker-compose.yml` with a small built-in YAML reader (real projects use PyYAML), lists the services, shows which URLs use service names, computes the start order from `depends_on`, and runs safety checks (pinned tags, ports on `127.0.0.1`, no secret written into the file, restart policies, healthchecks), first on the real file and then on an embedded careless one. Needs no Docker and no model.

**Expected output** (real run, trimmed):

```
Step 3: Start order from depends_on and healthchecks ───────────────────────────
  wave 1: chroma, redis
  wave 2: api, worker   [api waits for redis (service_healthy); api waits for chroma (service_started); worker waits for redis (service_healthy)]
service_started only waits for the process to exist; service_healthy waits for its healthcheck to pass.

Step 4: Safety and operations checks ───────────────────────────────────────────
  all checks pass
  secrets: LLM_API_KEY is not in this file; it arrives through env_file: .env

Step 5: The same checks on a careless file (embedded)
  FAIL db: image 'redis:latest' is not pinned to a tag
  FAIL db: port 6379:6379 is open to the network (bind to 127.0.0.1)
  ...
  FAIL api: OPENAI_API_KEY is written in the file
```

### 2. `02_queue_and_worker.py`: the API answers at once, the worker calls the model

```
./run 16.2/2
```

The queue pattern in one process: a FastAPI app (called through its test client) accepts four tickets and returns 202 in milliseconds; a worker thread does the model calls, retries a simulated transient error, and marks a deliberately crashing ticket `failed` after its capped retries. About 3-4 model calls. In compose the in-memory queue is Redis (`app/jobs.py`) and the worker is the `worker` service (`app/worker.py`).

**Expected output** (real run, trimmed):

```
Step 1: The API accepts every ticket without waiting for the model ─────────────
  POST /tickets -> 202 {'job_id': '018a2b8f', 'status': 'queued'}
  POST /tickets -> 202 {'job_id': '33d85ba2', 'status': 'queued'}
  POST /tickets -> 202 {'job_id': 'e1059888', 'status': 'queued'}
  POST /tickets -> 202 {'job_id': '857bf894', 'status': 'queued'}
  all 4 tickets accepted in 12 ms; queue length 4

Step 2: Start the worker and poll for results ──────────────────────────────────
  poll: ['queued', 'queued', 'queued', 'queued']
  poll: ['done', 'queued', 'queued', 'queued']
  worker: job e1059888 attempt 1 failed (TimeoutError), retrying
  poll: ['done', 'done', 'queued', 'queued']
  worker: job 857bf894 attempt 1 failed (RuntimeError), retrying
  poll: ['done', 'done', 'done', 'failed']

Step 3: The results ────────────────────────────────────────────────────────────
  [done  ] 'My VPN keeps dropping every few minutes.'
           -> Please try restarting your computer and clearing your VPN cache to resolve the connection instability. If the issue persists, please submit 
  [done  ] 'Outlook says my password is wrong after I cha'
           -> Please try restarting your computer to refresh your cached credentials with the server. If the issue persists, please contact the helpdesk s
  [done  ] 'The printer on floor 2 shows an offline error'
           -> Please try restarting the printer by unplugging it for 30 seconds and checking the network cable connection. If the error persists, please s
  [failed] 'BOOM-POISON this ticket always crashes the ha'
           -> error: RuntimeError
The poison ticket ended as 'failed' after its retries instead of looping forever or killing the worker.
In compose, results live in Redis, so the API container and the worker container can differ and restart independently.
```

The replies differ from run to run; the statuses (three `done`, one `failed`) and the retry lines are the point.

### 3. `03_redis_round_trip.py`: the queue on a real Redis

```
./run 16.2/3
```

Needs a Redis at `REDIS_URL`. It speaks Redis's text protocol with a few lines of sockets (`LPUSH`, `BRPOP`, `SET`, `GET`) on throwaway keys that it deletes at the end, so you see what the API and worker actually say to Redis. It does not call a model.

**Expected output without Redis** (real, from the author's machine, exit code 3):

```
╭─ This lesson needs Redis: REDIS_URL is not set. ─────────────────────────────╮
│ - Start one: docker run --rm -p 6379:6379 redis/redis-stack-server:latest    │
│ - Then set it in .env, for example REDIS_URL=redis://localhost:6379/0        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

With a Redis running, **you should see** `PING` answer `PONG`, `LPUSH` answer `1` (the list length), `BRPOP` return the key and the job JSON you pushed, then `SET` answer `OK` and `GET` return the result. This path was not run by the author.

### The shipped files

`docker-compose.yml` (four services, two volumes), `Dockerfile` (as in 16.1, health path `/health/live`), `pyproject.toml`, `.dockerignore`, `.env.example`, and `app/`: `api.py` (`POST /tickets`, `GET /tickets/{id}`, `/health/live`, `/health/ready`), `worker.py`, `jobs.py` (`MemoryQueue` and `RedisQueue`, one interface). To start it yourself (not run by the author):

```
cd modules/16-containers-and-deployment/02-docker-compose
cp .env.example .env        # edit the three LLM_ settings
docker compose up --build -d
docker compose ps           # wait for (healthy)
curl -X POST http://127.0.0.1:8000/tickets -H "Content-Type: application/json" -d '{"text":"My VPN keeps dropping."}'
curl http://127.0.0.1:8000/tickets/<job_id>
docker compose logs -f worker
docker compose down
```

## Try this

1. In `docker-compose.yml` change `service_healthy` to `service_started` for Redis and re-run script 1. What changes in the printed start order, and what could go wrong on a slow machine?
2. Add `ports: ["6379:6379"]` to Redis and run script 1. Which check fails, and why does it matter?
3. In script 2 raise `MAX_ATTEMPTS` to 3 and make the printer ticket fail twice. Does it still end `done`?
4. Add a second worker thread to script 2 (a second `Thread` on `worker`). Do the four tickets finish sooner? What would make two workers process the same job twice, and how does `BRPOP` avoid it in Redis?
5. Add a `scheduler` service to the compose file that reuses the image with another command, then run script 1.
6. (With Docker) run `docker compose up -d --scale worker=3` and `docker compose ps`; then stop one worker container and see whether the queue still drains.

## If it does not work

- Run `./run doctor`. The `apps` extra is installed with `./setup.sh --extra apps` (or `./setup.sh --all`).
- Scripts 1 and 2 need no Docker or Redis. Script 3 exits with code 3 and the start command if `REDIS_URL` is unset or Redis is not reachable.
- No Docker? Use a hosted Redis (any provider's free tier) and put its address in `.env`, for example `REDIS_URL=rediss://user:password@host:6380/0`. The API and worker read the same variable, so you can run them natively with `REDIS_URL` set (`uvicorn app.api:app`, `python -m app.worker`).
- `docker compose up` says the `.env` file is missing: copy `.env.example` to `.env` first.
- Containers cannot reach a model on your machine: use `host.docker.internal` instead of `localhost` in `LLM_BASE_URL` (see 16.1).

## In the running scenario

The Larkspur Labs helpdesk assistant stops answering inside the request. Tickets are accepted instantly, queued in Redis and answered by workers you can scale, with a vector store ready for the knowledge base. Nothing is lost when a container restarts, and nothing secret is in the compose file.

**Next:** 16.3 · Health checks, configuration and secrets (planned)

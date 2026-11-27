"""16.3/1  Three kinds of health check: live, ready, startup

One "/health" is not enough. Orchestrators ask three different questions:
  live     "is the process alive?"      -> if not, RESTART it
  ready    "can it serve right now?"    -> if not, stop SENDING TRAFFIC (do not restart)
  startup  "has it finished starting?"  -> until yes, do not judge it yet
Mixing them up causes outages: a liveness check that calls a database makes a database blip restart
every container at once. This script builds a small API with all three probes and drives it through
a dependency outage and a shutdown, in process (FastAPI's TestClient). No model call.

Run it:   ./run 16.3/1          (Windows: run 16.3/1)
"""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from labkit import lesson


class State:
    """What the probes look at. In a real app: set at startup, flipped by the shutdown handler."""

    started = False  # warm-up (load config, connect, load the knowledge base) finished
    draining = False  # we received SIGTERM: finish current work, take no new work
    queue_up = True  # stand-in for "Redis answers"
    model_configured = False


def build_app(state: State) -> FastAPI:
    app = FastAPI()

    @app.get("/health/live")
    def live() -> dict:
        # Cheap and dependency-free on purpose: it only proves the event loop answers.
        return {"status": "alive"}

    @app.get("/health/startup")
    def startup() -> dict:
        if not state.started:
            raise HTTPException(status_code=503, detail="still starting")
        return {"status": "started"}

    @app.get("/health/ready")
    def ready() -> dict:
        checks = {"started": state.started, "not_draining": not state.draining, "queue": state.queue_up, "model_settings": state.model_configured}
        if not all(checks.values()):
            raise HTTPException(status_code=503, detail=checks)
        return {"status": "ready", "checks": checks}

    return app


@lesson("16.3/1", "Liveness, readiness and startup probes")
def main(ctx):
    state = State()
    client = TestClient(build_app(state))

    def probe(label: str) -> None:
        row = []
        for name in ("live", "startup", "ready"):
            response = client.get(f"/health/{name}")
            row.append(f"{name}={response.status_code}")
        print(f"  {label:<44} " + "  ".join(row))

    ctx.step("The app is starting (warm-up not finished)")
    probe("process just started")
    ctx.note("live is 200 already, ready is 503: do not send traffic yet, and do not restart it either.")

    ctx.step("Warm-up done and settings loaded")
    state.started = True
    state.model_configured = True
    probe("healthy")

    ctx.step("The queue (Redis) goes down for a minute")
    state.queue_up = False
    probe("dependency outage")
    ctx.note("ready is 503 so the load balancer stops sending tickets; live stays 200 so nothing is restarted pointlessly.")
    print("  ready body:", client.get("/health/ready").json()["detail"])

    ctx.step("The queue recovers")
    state.queue_up = True
    probe("recovered")

    ctx.step("SIGTERM arrives (docker stop): drain")
    state.draining = True
    probe("draining")
    ctx.note("ready flips to 503 first, so no new request arrives while in-flight ones finish. Next script shows the handler.")

    ctx.step("What each probe must NOT do")
    print("  live    never calls the database, the queue or the MODEL: a slow provider must not make containers restart.")
    print("  ready   checks what THIS instance needs to serve (config, queue); keep it fast and cached for a few seconds.")
    print("  ready   should not call the model on every probe: it costs money and fails when the provider has a bad minute.")
    print("  startup gives slow starters (large indexes) a long allowance, e.g. Kubernetes startupProbe failureThreshold: 30.")
    print("  Docker's HEALTHCHECK is a single probe: point it at live; orchestrators (Kubernetes, Cloud Run) map all three.")


if __name__ == "__main__":
    main()

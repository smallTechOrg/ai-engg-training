"""16.2/3  Talk to the Redis from the compose stack (needs REDIS_URL)

Redis is the shared mailbox between the API container and the worker container. This script
speaks Redis's plain-text protocol (RESP) with a few lines of stdlib sockets, so you see exactly
what `LPUSH`, `BRPOP` and `SET` are, then does the queue round trip on a throwaway key
(`lesson-16-2:*`, deleted at the end). It does nothing else to your Redis.

Needs a Redis on REDIS_URL. The compose stack keeps Redis private (no published port), so start a
separate one for this script:
    docker run --rm -p 127.0.0.1:6379:6379 redis:7-alpine
then put REDIS_URL=redis://localhost:6379/0 in .env.

Run it:   ./run 16.2/3          (Windows: run 16.2/3)
"""

import json
import socket
from urllib.parse import urlparse

from labkit import lesson
from labkit.errors import ServiceUnavailable
from labkit.services import require

KEY = "lesson-16-2:jobs"
RESULT = "lesson-16-2:result:1"


def encode(*parts: str) -> bytes:
    """RESP request: *<count>, then $<length> and the bytes of each part."""
    out = f"*{len(parts)}\r\n".encode()
    for part in parts:
        data = part.encode()
        out += f"${len(data)}\r\n".encode() + data + b"\r\n"
    return out


def read_reply(stream):
    line = stream.readline().rstrip(b"\r\n")
    kind, rest = line[:1], line[1:]
    if kind in (b"+", b":"):
        return rest.decode()
    if kind == b"-":
        raise RuntimeError(rest.decode())
    if kind == b"$":
        if rest == b"-1":
            return None
        data = stream.read(int(rest) + 2)[:-2]
        return data.decode()
    if kind == b"*":
        return None if rest == b"-1" else [read_reply(stream) for _ in range(int(rest))]
    raise RuntimeError(f"unexpected reply {line!r}")


@lesson("16.2/3", "A queue round trip on Redis")
def main(ctx):
    url = require("REDIS_URL")
    parsed = urlparse(url)
    try:
        sock = socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), timeout=3)
    except OSError as exc:
        raise ServiceUnavailable("Redis did not accept a connection.", [f"Check REDIS_URL in .env ({type(exc).__name__})."]) from exc
    stream = sock.makefile("rb")

    def call(*parts: str):
        shown = " ".join(parts)
        sock.sendall(encode(*parts))
        reply = read_reply(stream)
        print(f"  > {shown[:70]:<70} {reply!r}"[:120])
        return reply

    try:
        ctx.step("Is it there?")
        call("PING")

        ctx.step("The API side: push a job on the list")
        job = json.dumps({"id": "1", "text": "My VPN keeps dropping."})
        call("LPUSH", KEY, job)

        ctx.step("The worker side: BRPOP takes the oldest job (waits up to 2 s)")
        popped = call("BRPOP", KEY, "2")
        job_back = json.loads(popped[1])
        print("  worker got:", job_back)

        ctx.step("The worker stores the result; the API reads it")
        call("SET", RESULT, json.dumps({"status": "done", "reply": "(model reply)"}), "EX", "60")
        call("GET", RESULT)
    finally:
        sock.sendall(encode("DEL", KEY, RESULT))
        read_reply(stream)
        sock.close()
    ctx.note("Throwaway keys deleted. LPUSH + BRPOP make a queue: producers and consumers never talk to each other, only to Redis.")


if __name__ == "__main__":
    main()

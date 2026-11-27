"""19.4/3  Capstone part 3: send the four scenarios to a real n8n

Needs n8n running with helpdesk-ticket-agent-workflow.json imported (and, for the success paths, the triage
agent reachable from n8n at the URL in the 'Triage agent' node). Sends the same four requests as script 2 to
the intake webhook and prints each status and body. With n8n absent the script exits 3 with the start command.

Run it:   ./run 19.4/3 [--production]       (Windows: run 19.4/3)
     or:  python modules/19-workflow-automation-n8n/04-capstone-a-helpdesk-ticket-workflow-calling-an-a/03_trigger_the_real_workflow.py
"""

import json
import sys
import urllib.error
import urllib.request

from labkit import lesson
from labkit.services import require

REQUESTS = [
    ("urgent ticket", {"ticket": "The whole floor 3 has lost wifi and nobody can work."}),
    ("routine ticket", {"ticket": "Please reset my password for the Larkspur wiki when you can."}),
    ("empty ticket", {"ticket": ""}),
]


@lesson("19.4/3", "Capstone part 3: send the scenarios to a real n8n")
def main(ctx):
    base = require("N8N_URL").rstrip("/")
    kind = "webhook" if "--production" in sys.argv else "webhook-test"
    url = f"{base}/{kind}/helpdesk-intake"
    if kind == "webhook-test":
        ctx.note("Test URLs listen once: click 'Listen for test event' before EACH request, or use --production with the workflow Active.")
    for label, body in REQUESTS:
        ctx.step(f"{label}: POST {url}")
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            status, text = err.code, err.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as err:
            ctx.note(f"Could not reach n8n: {err}")
            return
        print(f"  status {status}: {text[:500]}")
    ctx.note("Compare with script 2: the urgent ticket should be 'escalated', the routine one 'queued', the empty one 422.")


if __name__ == "__main__":
    main()
